"""
評価レコードの DB 一括保存モジュール (Issue #716)
"""

import logging
import random
import threading
import time
from typing import Any

from django.db import OperationalError, close_old_connections

logger = logging.getLogger(__name__)

from package.ml.constants import EVAL_DB_WRITE_BATCH_SIZE
from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.models.evaluation import PropertyEvaluation

BASE_UPDATE_FIELDS = (
    "company", "property_type", "property_id", "first_stage_predicted_price",
    "first_stage_p10_price", "prediction_uncertainty_ratio",
    "is_first_stage_passed", "analysis_status", "analyzed_at", "duplicate_of", "is_slack_notified",
    "estimated_sekisan_price", "monthly_land_rent", "land_rent_liability",
    "expected_gross_yield", "expected_net_yield", "estimated_annual_rent", "dcf_theoretical_price",
    "is_psychological_defect", "is_as_is_condition", "is_boundary_unspecified",
    "is_unbuildable", "is_urbanization_control_area", "has_private_road_burden",
    "is_sublease", "bath_type", "gas_type", "sewage_type",
    "has_elevator", "is_stair_only_3f_plus", "is_old_earthquake_standard",
)
INVESTMENT_UPDATE_FIELDS = (
    "net_operating_income", "debt_service",
    "dscr", "total_investment_score",
)
EVAL_MAP_FIELDS = (
    "id", "property_url", "second_stage_predicted_price", "is_published", "needs_recrawl",
) + BASE_UPDATE_FIELDS + INVESTMENT_UPDATE_FIELDS

CANDIDATE_POOL_TTL_SEC = 60.0
_CANDIDATE_CACHE_LOCK = threading.Lock()
_CANDIDATE_POOL_CACHE: dict[str, tuple[float, int, list[PropertyEvaluation]]] = {}


def clear_candidate_pool_cache() -> None:
    """重複照合用の候補プールTTLキャッシュをクリアする。"""
    with _CANDIDATE_CACHE_LOCK:
        _CANDIDATE_POOL_CACHE.clear()


def _pk_sort_key(rec: Any) -> tuple[int, Any]:
    pk_val = getattr(rec, "pk", None)
    if isinstance(pk_val, int):
        return (0, pk_val)
    return (1, str(pk_val))


def bulk_update_evaluation_records(
    records_to_update: list[Any],
    property_type: str = "",
    batch_size: int = EVAL_DB_WRITE_BATCH_SIZE,
) -> None:
    """更新対象レコードの重複を除去し、PK昇順ソートでデッドロックを防止して bulk_update を実行する"""
    valid_updates = []
    seen_pks = set()
    for r in records_to_update:
        if r.pk and r.pk not in seen_pks:
            seen_pks.add(r.pk)
            valid_updates.append(r)

    if not valid_updates:
        return

    valid_updates.sort(key=_pk_sort_key)

    update_fields = list(BASE_UPDATE_FIELDS)
    if "investment" in property_type or "invest" in property_type:
        update_fields.extend(INVESTMENT_UPDATE_FIELDS)
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            PropertyEvaluation.objects.bulk_update(
                valid_updates,
                fields=update_fields,
                batch_size=batch_size,
            )
            break
        except OperationalError as e:
            logger.warning("bulk_update failed on attempt %d/%d: %s", attempt, max_retries, e)
            close_old_connections()
            if attempt == max_retries:
                raise
            wait_s = min(8.0, 0.5 * (2 ** (attempt - 1)) + random.uniform(0.05, 0.35))
            time.sleep(wait_s)


def _bulk_create_records(records_to_create: list[Any], batch_size: int) -> None:
    """重複URLを除去して bulk_create を実行する"""
    if not records_to_create:
        return
    unique_creates = []
    seen_create_urls = set()
    for r in records_to_create:
        if r.property_url and r.property_url not in seen_create_urls:
            seen_create_urls.add(r.property_url)
            unique_creates.append(r)
    if unique_creates:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                PropertyEvaluation.objects.bulk_create(
                    unique_creates,
                    batch_size=batch_size,
                    ignore_conflicts=True,
                )
                break
            except OperationalError as e:
                logger.warning("bulk_create failed on attempt %d/%d: %s", attempt, max_retries, e)
                close_old_connections()
                if attempt == max_retries:
                    raise
                time.sleep(1.0 * attempt)


def _prefetch_candidate_pool(
    existing_eval_map: dict[str, Any],
    property_type: str,
) -> list[PropertyEvaluation] | None:
    """チャンク内の最小IDより前の重複候補を一括プリフェッチする（種別単位のTTLキャッシュ対応）"""
    from package.utils.deduplication import _prefetch_real_properties

    existing_ids = [e.id for e in existing_eval_map.values() if e and e.id is not None]
    if not existing_ids:
        return None
    min_id = min(existing_ids)
    now_mono = time.monotonic()

    with _CANDIDATE_CACHE_LOCK:
        cached = _CANDIDATE_POOL_CACHE.get(property_type)
        if cached is not None and (now_mono - cached[0]) <= CANDIDATE_POOL_TTL_SEC and min_id >= cached[1]:
            return [c for c in cached[2] if getattr(c, "id", 0) < min_id]

    try:
        candidate_pool = list(
            PropertyEvaluation.objects.filter(property_type=property_type, id__lt=min_id)
            .select_related("duplicate_of")
            .order_by("-id")[:100]
        )
        if candidate_pool:
            _prefetch_real_properties(candidate_pool)
        with _CANDIDATE_CACHE_LOCK:
            _CANDIDATE_POOL_CACHE[property_type] = (now_mono, min_id, candidate_pool)
        return candidate_pool
    except Exception as e:
        logger.debug("Candidate pool prefetch failed: %s", e)
        return None


def save_chunk(
    chunk: list[Any],
    predicted_prices: list[float],
    existing_eval_map: dict[str, Any],
    company: str,
    property_type: str,
    batch_size: int,
    skip_duplicate_check: bool = False,
    p10_prices: list[float] | None = None,
) -> tuple[int, int]:
    """チャンク内の物件を評価しDBに一括保存する（新規作成と更新を分離処理・重複候補一括プリフェッチ）"""
    records_to_create = []
    records_to_update = []
    chunk_passed = 0
    chunk_duplicates = 0

    candidate_pool = _prefetch_candidate_pool(existing_eval_map, property_type) if not skip_duplicate_check else None

    for idx, (item, price_stage1) in enumerate(zip(chunk, predicted_prices)):
        page_url = str(getattr(item, "pageUrl", None) or getattr(item, "url", None) or "")
        existing = existing_eval_map.get(page_url) if page_url else None
        p10_val = float(p10_prices[idx]) if p10_prices is not None and idx < len(p10_prices) else None
        rec, is_new = build_or_update_eval_record(
            item=item,
            price_stage1=price_stage1,
            existing=existing,
            company=company,
            property_type=property_type,
            candidate_pool=candidate_pool,
            skip_duplicate_check=skip_duplicate_check,
            p10_stage1=p10_val,
        )
        if rec.is_first_stage_passed:
            chunk_passed += 1
        if getattr(rec, "duplicate_of_id", None):
            chunk_duplicates += 1
        if is_new:
            records_to_create.append(rec)
        else:
            records_to_update.append(rec)

    _bulk_create_records(records_to_create, batch_size)
    if records_to_update:
        bulk_update_evaluation_records(records_to_update, property_type, batch_size)

    return chunk_passed, chunk_duplicates
