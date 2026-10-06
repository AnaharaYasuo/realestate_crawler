"""
不整合データ (needs_parser_fix=True) の分散再クローリングバッチ (Issue #735)

Cloud Run Jobs タスクアレイ (8並列) および通常クローラー同一並行度 (DETAIL_PARARELL_LIMIT=3) で
異常物件のみをピンポイント再巡回し、最新化・フラグ解消・掲載終了反映を行う。
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import Any

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

from asgiref.sync import sync_to_async
from django.db.models import F
from package.api.mitsui import DETAIL_PARARELL_LIMIT
from package.models.evaluation import PropertyEvaluation
from package.utils.task_distribution import get_task_config
from package.utils.url_router import UrlRouter

logger = logging.getLogger(__name__)

# サーキットブレイカー: 連続タイムアウトFast-Fail上限
MAX_CONSECUTIVE_TIMEOUTS = 3


def filter_targets_by_task(records: list[Any], task_index: int | None, task_count: int) -> list[Any]:
    """対象レコードを Cloud Run Jobs タスクアレイの Modulo 分割により抽出する (後方互換/単体テスト用)"""
    if task_index is None or task_count <= 1:
        return records
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")
    return [rec for rec in records if (getattr(rec, "property_id", 0) or 0) % task_count == task_index]


def fetch_assigned_targets(task_index: int | None, task_count: int, limit: int | None = None) -> list[Any]:
    """各タスクの担当条件(Modulo)と--limitをDjangoクエリに直接適用して取得する"""
    qs = PropertyEvaluation.objects.filter(needs_parser_fix=True, is_published=True)
    if task_index is not None and task_count > 1:
        # Django DB 側で Modulo フィルタを適用し、不要な全件ロードを抑制
        qs = qs.annotate(mod_id=F("property_id") % task_count).filter(mod_id=task_index)
    qs = qs.order_by("property_id")
    if limit and limit > 0:
        qs = qs[:limit]
    return list(qs)


class AnomalyDetailRunner:
    """単一URLの再取得を実行する軽量 Runner"""
    def __init__(self, url: str):
        self.url = url
        self.parser = UrlRouter.create_parser(url)

    async def run(self):
        if not self.parser:
            logger.warning("No parser resolved for URL: %s", self.url)
            return None
        from package.api.api import ParseDetailPageAsyncBase

        class DirectDetailProc(ParseDetailPageAsyncBase):
            def __init__(outer_self):
                super().__init__()
                outer_self.parser = self.parser
                outer_self.url = self.url

            def _generateParser(outer_self):
                return self.parser

            def _getLocalPararellLimit(outer_self):
                return DETAIL_PARARELL_LIMIT

            def _getCloudPararellLimit(outer_self):
                return DETAIL_PARARELL_LIMIT

            def _getTimeOutSecond(outer_self):
                return 60

            def _getApiKey(outer_self):
                return ""

        proc = DirectDetailProc()
        return await proc._run(self.url)


class CircuitBreakerState:
    """連続タイムアウト・接続失敗を監視するサーキットブレイカー"""
    def __init__(self, threshold: int = MAX_CONSECUTIVE_TIMEOUTS):
        self.consecutive_failures = 0
        self.is_tripped = False
        self.threshold = threshold
        self.lock = asyncio.Lock()

    async def record_success(self):
        async with self.lock:
            self.consecutive_failures = 0

    async def record_failure(self, is_timeout_or_connection: bool):
        async with self.lock:
            if is_timeout_or_connection:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.threshold:
                    self.is_tripped = True
                    logger.error(
                        "Circuit breaker TRIPPED: %d consecutive timeouts/connection errors. Aborting remaining recrawls.",
                        self.consecutive_failures,
                    )
            else:
                self.consecutive_failures = 0


async def _recrawl_single_url(
    sem: asyncio.Semaphore,
    eval_rec: Any,
    circuit_breaker: CircuitBreakerState,
) -> str:
    """単一物件の再取得を実行し、永続化後のステータス (resolved, delisted, unresolved, failed, skipped) を返す"""
    if circuit_breaker.is_tripped:
        return "skipped_by_circuit_breaker"

    url = eval_rec.property_url
    async with sem:
        if circuit_breaker.is_tripped:
            return "skipped_by_circuit_breaker"
        try:
            logger.info("Recrawling anomaly URL: %s", url)
            runner = AnomalyDetailRunner(url)
            item = await runner.run()
        except (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError):
            await circuit_breaker.record_failure(is_timeout_or_connection=True)
            logger.exception("Timeout or connection failure recrawling %s", url)
            return "failed"
        except Exception:
            await circuit_breaker.record_failure(is_timeout_or_connection=False)
            logger.exception("Failed recrawling anomaly URL %s", url)
            return "failed"

        # 永続化後の最新レコード状態を確認して分類
        def get_post_state():
            latest = PropertyEvaluation.objects.filter(property_url=url).first()
            if not latest:
                return "failed"
            if not latest.is_published:
                return "delisted"
            if item is not None and not latest.needs_parser_fix:
                return "resolved"
            return "failed" if item is None else "unresolved"

        outcome = await sync_to_async(get_post_state)()
        if outcome in ("resolved", "delisted"):
            await circuit_breaker.record_success()
        else:
            await circuit_breaker.record_failure(is_timeout_or_connection=False)

        return outcome


async def recrawl_anomalies_async(
    task_index: int | None = None,
    task_count: int = 8,
    concurrency: int = DETAIL_PARARELL_LIMIT,
    limit: int | None = None,
    dry_run: bool = False,
):
    """不整合物件の分散再クローリング本体ロジック"""
    # 1. 担当条件と上限を DB クエリに直接適用して取得
    my_targets = await sync_to_async(fetch_assigned_targets)(task_index=task_index, task_count=task_count, limit=limit)
    logger.info(
        "Task [%s/%d]: Assigned %d properties to recrawl (Concurrency: %d, DryRun: %s)",
        task_index, task_count, len(my_targets), concurrency, dry_run
    )

    if dry_run or not my_targets:
        return len(my_targets), {}

    # 2. セマフォ制御 & サーキットブレイカー付き並行実行
    sem = asyncio.Semaphore(concurrency)
    circuit_breaker = CircuitBreakerState()
    tasks = [_recrawl_single_url(sem, rec, circuit_breaker) for rec in my_targets]
    outcomes = await asyncio.gather(*tasks)

    # 3. 結果の集計 (resolved, delisted, unresolved, failed, skipped_by_circuit_breaker)
    stats: dict[str, int] = {}
    for outcome in outcomes:
        stats[outcome] = stats.get(outcome, 0) + 1

    logger.info(
        "Finished recrawl for task [%s/%d]: Total %d, Stats: %s",
        task_index, task_count, len(my_targets), stats
    )
    return len(my_targets), stats


def main():
    parser = argparse.ArgumentParser(description="Distributed recrawling for needs_parser_fix properties")
    parser.add_argument("--task-index", type=int, default=None, help="Cloud Run Task Index (0-based)")
    parser.add_argument("--task-count", type=int, default=None, help="Total Cloud Run Tasks (default: 8)")
    parser.add_argument("--concurrency", type=int, default=None, help=f"In-process concurrency (default: {DETAIL_PARARELL_LIMIT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to recrawl")
    parser.add_argument("--dry-run", action="store_true", help="Simulate task allocation without fetching")
    args = parser.parse_args()

    env_index, env_count = get_task_config()
    task_index = args.task_index if args.task_index is not None else env_index
    task_count = args.task_count if args.task_count is not None else (env_count if env_count > 1 else 8)

    cloud_concurrency_env = os.getenv("CLOUD_DETAIL_CONCURRENCY")
    default_concurrency = int(cloud_concurrency_env) if cloud_concurrency_env and cloud_concurrency_env.isdigit() else DETAIL_PARARELL_LIMIT
    concurrency = args.concurrency if args.concurrency is not None else default_concurrency

    _, stats = asyncio.run(
        recrawl_anomalies_async(
            task_index=task_index,
            task_count=task_count,
            concurrency=concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )

    failed_cnt = stats.get("failed", 0)
    circuit_cnt = stats.get("skipped_by_circuit_breaker", 0)
    if failed_cnt > 0 or circuit_cnt > 0:
        logger.error(
            "Recrawl finished with errors (Failed: %d, Skipped by circuit breaker: %d)",
            failed_cnt, circuit_cnt
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
