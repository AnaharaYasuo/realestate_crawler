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
from django.db.models import F, Q
from django.utils import timezone
from package.api.mitsui import DETAIL_PARARELL_LIMIT
from package.models.evaluation import PropertyEvaluation
from package.site_registry import SiteRegistry
from package.utils.git_version import get_current_git_sha
from package.utils.task_distribution import get_task_config
from package.utils.url_router import UrlRouter

logger = logging.getLogger(__name__)

# サーキットブレイカー: 連続タイムアウトFast-Fail上限
MAX_CONSECUTIVE_TIMEOUTS = 3
SOURCE_INVALID_RECRAWL_THRESHOLD = 3


class TargetPropertyRef:
    """汎用再クローリング対象参照オブジェクト"""
    def __init__(self, property_url: str, property_id: int = 0):
        self.property_url = property_url
        self.property_id = property_id


def _resolve_shard_key(rec: Any) -> int:
    pk_val = getattr(rec, "id", None)
    if isinstance(pk_val, int):
        return pk_val
    prop_id = getattr(rec, "property_id", 0)
    return prop_id if isinstance(prop_id, int) else 0


def filter_targets_by_task(records: list[Any], task_index: int | None, task_count: int) -> list[Any]:
    """対象レコードを Cloud Run Jobs タスクアレイの Modulo 分割により抽出する (property_id=0 の Task 0 集中防止のため PK id 優先)"""
    if task_index is None or task_count <= 1:
        return records
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")
    return [rec for rec in records if _resolve_shard_key(rec) % task_count == task_index]


def fetch_assigned_targets(
    task_index: int | None,
    task_count: int,
    limit: int | None = None,
    urls: list[str] | None = None,
    model_name: str | None = None,
    field_empty: str | None = None,
    company: str | None = None,
    include_needs_recrawl: bool = True,
    skip_same_sha: bool = False,
) -> list[Any]:
    """各タスクの担当条件(Modulo)と--limitをDjangoクエリに直接適用して取得する"""
    if urls:
        targets = [TargetPropertyRef(u.strip(), idx) for idx, u in enumerate(urls) if u.strip()]
        filtered = filter_targets_by_task(targets, task_index=task_index, task_count=task_count)
        return filtered[:limit] if (limit and limit > 0) else filtered

    if model_name:
        from django.apps import apps
        model = apps.get_model("package", model_name)
        qs = model.objects.all()
        if field_empty:
            qs = qs.filter(Q(**{field_empty: ""}) | Q(**{f"{field_empty}__isnull": True}))
        if task_index is not None and task_count > 1:
            qs = qs.annotate(mod_id=F("id") % task_count).filter(mod_id=task_index)
        qs = qs.order_by("id")
        if limit and limit > 0:
            qs = qs[:limit]
        return [TargetPropertyRef(getattr(item, "pageUrl", ""), item.id) for item in qs.only("id", "pageUrl")]

    flag_q = Q(needs_parser_fix=True) | Q(needs_recrawl=True) if include_needs_recrawl else Q(needs_parser_fix=True)
    qs = PropertyEvaluation.objects.filter(flag_q, is_published=True).exclude(heal_status="source_data_invalid")
    if company:
        qs = qs.filter(company=company)
    if skip_same_sha:
        current_sha = get_current_git_sha()
        if current_sha:
            qs = qs.exclude(failed_git_sha=current_sha, recrawl_attempts__gte=1)
    if task_index is not None and task_count > 1:
        # property_id=0 (初回パース例外レコード) が Task 0 に100%集中するのを防ぐため PropertyEvaluation.id で均等分割
        qs = qs.annotate(mod_id=F("id") % task_count).filter(mod_id=task_index)
    qs = qs.order_by("id")
    if limit and limit > 0:
        qs = qs[:limit]
    return list(qs)


def apply_unresolved_recrawl_escalation(
    eval_rec: Any,
    current_sha: str | None = None,
    item_parsed: bool = True,
    now: Any = None,
) -> None:
    """Update recrawl_attempts across distinct Git SHAs and isolate source_data_invalid after 3 attempts (Issue #1410)."""
    sha = (current_sha if current_sha is not None else get_current_git_sha()) or ""
    ts = now if now is not None else timezone.now()
    prev_sha = (getattr(eval_rec, "failed_git_sha", "") or "").strip()
    attempts = int(getattr(eval_rec, "recrawl_attempts", 0) or 0)

    if not sha or sha != prev_sha or attempts == 0:
        attempts += 1

    eval_rec.recrawl_attempts = attempts
    eval_rec.last_recrawled_at = ts
    if sha:
        eval_rec.failed_git_sha = sha

    if item_parsed and attempts >= SOURCE_INVALID_RECRAWL_THRESHOLD:
        eval_rec.heal_status = "source_data_invalid"
        eval_rec.needs_parser_fix = False
        eval_rec.needs_recrawl = False


def cleanup_orphaned_old_type_record(
    old_company: str | None,
    old_property_type: str | None,
    old_property_id: int | None,
    new_company: str | None,
    new_property_type: str | None,
    property_url: str,
) -> bool:
    """Delete stale row from previous property-type table when parser type-switch healed the URL (Issue #1410)."""
    if not old_company or not old_property_type or not new_company or not new_property_type:
        return False
    if old_company == new_company and old_property_type == new_property_type:
        return False

    old_model = SiteRegistry.resolve_model_class(old_company, old_property_type)
    new_model = SiteRegistry.resolve_model_class(new_company, new_property_type)
    if old_model is None or old_model is new_model:
        return False

    from package.utils.url_matcher import UrlMatcher

    norm_url = UrlMatcher.normalize(property_url)
    url_q = Q(pageUrl=property_url) | Q(pageUrl=norm_url)
    if old_property_id and old_property_id > 0:
        qs = old_model.objects.filter(Q(id=old_property_id) | url_q)
    else:
        qs = old_model.objects.filter(url_q)
    qs.delete()
    logger.info(
        "[Orphan Cleanup] Removed stale record in %s for %s (migrated %s/%s -> %s/%s)",
        getattr(old_model, "__name__", str(old_model)),
        property_url,
        old_company,
        old_property_type,
        new_company,
        new_property_type,
    )
    return True


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


def _evaluate_post_recrawl_state(
    url: str,
    item: Any,
    old_company: str | None,
    old_property_type: str | None,
    old_property_id: int | None,
) -> str:
    from package.utils.url_matcher import UrlMatcher

    normalized_url = UrlMatcher.normalize(url)
    latest = (
        PropertyEvaluation.objects.filter(property_url=url).first()
        or PropertyEvaluation.objects.filter(property_url=normalized_url).first()
        or UrlMatcher.find_match_in_queryset(PropertyEvaluation.objects, "property_url", url)
    )
    if not latest:
        return "failed"
    if not latest.is_published:
        return "delisted"
    if item is not None:
        cleanup_orphaned_old_type_record(
            old_company=old_company,
            old_property_type=old_property_type,
            old_property_id=old_property_id,
            new_company=getattr(latest, "company", None),
            new_property_type=getattr(latest, "property_type", None),
            property_url=url,
        )
    if item is not None and not latest.needs_parser_fix and not latest.needs_recrawl:
        latest.last_recrawled_at = timezone.now()
        try:
            latest.save(update_fields=["last_recrawled_at"])
        except Exception:  # noqa: BLE001
            pass
        return "resolved"

    apply_unresolved_recrawl_escalation(latest, item_parsed=item is not None)
    try:
        latest.save(
            update_fields=[
                "recrawl_attempts",
                "last_recrawled_at",
                "failed_git_sha",
                "heal_status",
                "needs_parser_fix",
                "needs_recrawl",
            ]
        )
    except Exception:  # noqa: BLE001
        pass
    return "failed" if item is None else "unresolved"


async def _recrawl_single_url(
    sem: asyncio.Semaphore,
    eval_rec: Any,
    circuit_breaker: CircuitBreakerState,
) -> str:
    """単一物件の再取得を実行し、永続化後のステータス (resolved, delisted, unresolved, failed, skipped) を返す"""
    if circuit_breaker.is_tripped:
        return "skipped_by_circuit_breaker"

    url = getattr(eval_rec, "property_url", None) or getattr(eval_rec, "pageUrl", None) or str(eval_rec)
    old_company = getattr(eval_rec, "company", None)
    old_property_type = getattr(eval_rec, "property_type", None)
    old_property_id = getattr(eval_rec, "property_id", None)
    async with sem:
        if circuit_breaker.is_tripped:
            return "skipped_by_circuit_breaker"
        try:
            logger.info("Recrawling target URL: %s", url)
            runner = AnomalyDetailRunner(url)
            item = await runner.run()
        except (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError):
            await circuit_breaker.record_failure(is_timeout_or_connection=True)
            logger.exception("Timeout or connection failure recrawling %s", url)
            return "failed"
        except Exception:
            await circuit_breaker.record_failure(is_timeout_or_connection=False)
            logger.exception("Failed recrawling target URL %s", url)
            return "failed"

        outcome = await sync_to_async(_evaluate_post_recrawl_state)(
            url, item, old_company, old_property_type, old_property_id
        )
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
    urls: list[str] | None = None,
    model_name: str | None = None,
    field_empty: str | None = None,
    company: str | None = None,
    include_needs_recrawl: bool = True,
    skip_same_sha: bool = False,
):
    """不整合物件および指定対象物件の分散再クローリング本体ロジック"""
    # 1. 担当条件と上限を DB クエリに直接適用して取得
    my_targets = await sync_to_async(fetch_assigned_targets)(
        task_index=task_index,
        task_count=task_count,
        limit=limit,
        urls=urls,
        model_name=model_name,
        field_empty=field_empty,
        company=company,
        include_needs_recrawl=include_needs_recrawl,
        skip_same_sha=skip_same_sha,
    )
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
    parser = argparse.ArgumentParser(description="Distributed recrawling for needs_parser_fix/needs_recrawl properties")
    parser.add_argument("--task-index", type=int, default=None, help="Cloud Run Task Index (0-based)")
    parser.add_argument("--task-count", type=int, default=None, help="Total Cloud Run Tasks (default: 8)")
    parser.add_argument("--concurrency", type=int, default=None, help=f"In-process concurrency (default: {DETAIL_PARARELL_LIMIT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to recrawl")
    parser.add_argument("--dry-run", action="store_true", help="Simulate task allocation without fetching")
    parser.add_argument("--urls", type=str, default=None, help="Comma-separated target URLs to recrawl directly")
    parser.add_argument("--model", type=str, default=None, help="Target model name (e.g. NomuraKodate)")
    parser.add_argument("--field-empty", type=str, default=None, help="Field name that is empty (e.g. madori)")
    parser.add_argument("--company", type=str, default=None, help="Filter by company name (e.g. homes)")
    parser.add_argument("--include-needs-recrawl", action="store_true", default=True, help="Include needs_recrawl=True records (enabled by default)")
    parser.add_argument("--only-parser-fix", action="store_true", help="Restrict recrawl strictly to needs_parser_fix=True")
    parser.add_argument("--skip-same-sha", action="store_true", help="Skip records that already failed on the current Git SHA")
    args = parser.parse_args()

    env_index, env_count = get_task_config()
    task_index = args.task_index if args.task_index is not None else env_index
    task_count = args.task_count if args.task_count is not None else (env_count if env_count > 1 else 8)

    cloud_concurrency_env = os.getenv("CLOUD_DETAIL_CONCURRENCY")
    default_concurrency = int(cloud_concurrency_env) if cloud_concurrency_env and cloud_concurrency_env.isdigit() else DETAIL_PARARELL_LIMIT
    concurrency = args.concurrency if args.concurrency is not None else default_concurrency

    url_list = [u.strip() for u in args.urls.split(",") if u.strip()] if args.urls else None
    include_recrawl = False if args.only_parser_fix else bool(args.include_needs_recrawl)

    _, stats = asyncio.run(
        recrawl_anomalies_async(
            task_index=task_index,
            task_count=task_count,
            concurrency=concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
            urls=url_list,
            model_name=args.model,
            field_empty=args.field_empty,
            company=args.company,
            include_needs_recrawl=include_recrawl,
            skip_same_sha=args.skip_same_sha,
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
