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

from package.api.mitsui import DETAIL_PARARELL_LIMIT
from package.models.evaluation import PropertyEvaluation
from package.utils.task_distribution import get_task_config
from package.utils.url_router import UrlRouter

logger = logging.getLogger(__name__)


def filter_targets_by_task(records: list[Any], task_index: int | None, task_count: int) -> list[Any]:
    """
    対象レコードを Cloud Run Jobs タスクアレイの Modulo 分割により抽出する
    """
    if task_index is None or task_count <= 1:
        return records
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")
    return [rec for rec in records if (getattr(rec, "property_id", 0) or 0) % task_count == task_index]


class AnomalyDetailRunner:
    """単一URLの再取得を実行する軽量 Runner"""
    def __init__(self, url: str):
        self.url = url
        self.parser = UrlRouter.create_parser(url)

    async def run(self):
        if not self.parser:
            logger.warning("No parser resolved for URL: %s", self.url)
            return None
        # 詳細取得基底クラスの仕組みを直接利用して最新取得
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


async def _recrawl_single_url(sem: asyncio.Semaphore, eval_rec: Any) -> tuple[str, bool]:
    """単一物件の再取得をセマフォ制御下で実行"""
    url = eval_rec.property_url
    async with sem:
        try:
            logger.info("Recrawling anomaly URL: %s", url)
            runner = AnomalyDetailRunner(url)
            item = await runner.run()
            success = item is not None
            return url, success
        except Exception:
            logger.exception("Failed recrawling anomaly URL %s", url)
            return url, False


async def recrawl_anomalies_async(
    task_index: int | None = None,
    task_count: int = 8,
    concurrency: int = DETAIL_PARARELL_LIMIT,
    limit: int | None = None,
    dry_run: bool = False,
):
    """
    不整合物件の分散再クローリング本体ロジック
    """
    # 1. 対象レコード取得 (needs_parser_fix=True かつ 公開中)
    from asgiref.sync import sync_to_async
    def fetch_records():
        return list(PropertyEvaluation.objects.filter(needs_parser_fix=True, is_published=True).order_by("property_id"))

    all_targets = await sync_to_async(fetch_records)()
    logger.info("Found total %d candidate properties with needs_parser_fix=True", len(all_targets))

    # 2. タスクアレイによる担当物件の分割
    my_targets = filter_targets_by_task(all_targets, task_index=task_index, task_count=task_count)
    if limit and limit > 0:
        my_targets = my_targets[:limit]

    logger.info(
        "Task [%s/%d]: Assigned %d properties to recrawl (Concurrency: %d, DryRun: %s)",
        task_index, task_count, len(my_targets), concurrency, dry_run
    )

    if dry_run or not my_targets:
        return len(my_targets), 0

    # 3. セマフォ制御並行実行 (通常クローラーと同一並行度)
    sem = asyncio.Semaphore(concurrency)
    tasks = [_recrawl_single_url(sem, rec) for rec in my_targets]
    results = await asyncio.gather(*tasks)

    success_cnt = sum(1 for _, ok in results if ok)
    logger.info("Finished recrawl for task [%s/%d]: Success %d / Total %d", task_index, task_count, success_cnt, len(my_targets))
    return len(my_targets), success_cnt


def main():
    parser = argparse.ArgumentParser(description="Distributed recrawling for needs_parser_fix properties")
    parser.add_argument("--task-index", type=int, default=None, help="Cloud Run Task Index (0-based)")
    parser.add_argument("--task-count", type=int, default=None, help="Total Cloud Run Tasks (default: 8)")
    parser.add_argument("--concurrency", type=int, default=None, help=f"In-process concurrency (default: {DETAIL_PARARELL_LIMIT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to recrawl")
    parser.add_argument("--dry-run", action="store_true", help="Simulate task allocation without fetching")
    args = parser.parse_args()

    # 環境変数から Cloud Run Jobs 設定を自動検出
    env_index, env_count = get_task_config()
    task_index = args.task_index if args.task_index is not None else env_index
    task_count = args.task_count if args.task_count is not None else (env_count if env_count > 1 else 8)

    cloud_concurrency_env = os.getenv("CLOUD_DETAIL_CONCURRENCY")
    default_concurrency = int(cloud_concurrency_env) if cloud_concurrency_env and cloud_concurrency_env.isdigit() else DETAIL_PARARELL_LIMIT
    concurrency = args.concurrency if args.concurrency is not None else default_concurrency

    asyncio.run(
        recrawl_anomalies_async(
            task_index=task_index,
            task_count=task_count,
            concurrency=concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
