"""
評価レコードの DB 一括保存モジュール (Issue #716)
"""

from typing import Any

from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.models.evaluation import PropertyEvaluation

BASE_UPDATE_FIELDS = (
    "company", "property_type", "property_id", "first_stage_predicted_price",
    "is_first_stage_passed", "analysis_status", "duplicate_of", "is_slack_notified",
    "monthly_land_rent", "land_rent_liability",
    "is_psychological_defect", "is_as_is_condition", "is_boundary_unspecified",
    "is_unbuildable", "is_urbanization_control_area", "has_private_road_burden",
    "is_sublease", "bath_type", "gas_type", "sewage_type",
    "has_elevator", "is_stair_only_3f_plus", "is_old_earthquake_standard",
)
INVESTMENT_UPDATE_FIELDS = (
    "estimated_sekisan_price", "net_operating_income", "debt_service",
    "dscr", "total_investment_score",
)
EVAL_MAP_FIELDS = (
    "id", "property_url", "second_stage_predicted_price", "is_published", "needs_recrawl",
) + BASE_UPDATE_FIELDS + INVESTMENT_UPDATE_FIELDS


def bulk_update_evaluation_records(
    records_to_update: list[Any],
    property_type: str,
    batch_size: int,
) -> None:
    """更新対象レコードの重複を除去して bulk_update を実行する"""
    valid_updates = []
    seen_pks = set()
    for r in records_to_update:
        if r.pk and r.pk not in seen_pks:
            seen_pks.add(r.pk)
            valid_updates.append(r)

    if not valid_updates:
        return

    update_fields = list(BASE_UPDATE_FIELDS)
    if "investment" in property_type or "invest" in property_type:
        update_fields.extend(INVESTMENT_UPDATE_FIELDS)
    PropertyEvaluation.objects.bulk_update(
        valid_updates,
        fields=update_fields,
        batch_size=batch_size,
    )


def save_chunk(
    chunk: list[Any],
    predicted_prices: list[float],
    existing_eval_map: dict[str, Any],
    company: str,
    property_type: str,
    batch_size: int,
) -> tuple[int, int]:
    """チャンク内の物件を評価しDBに一括保存する（新規作成と更新を分離処理）"""
    records_to_create = []
    records_to_update = []
    chunk_passed = 0
    chunk_duplicates = 0

    for item, price_stage1 in zip(chunk, predicted_prices):
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        existing = existing_eval_map.get(page_url)
        rec, is_new = build_or_update_eval_record(item, price_stage1, existing, company, property_type)
        if rec.is_first_stage_passed:
            chunk_passed += 1
        if getattr(rec, "duplicate_of_id", None):
            chunk_duplicates += 1
        if is_new:
            records_to_create.append(rec)
        else:
            records_to_update.append(rec)

    if records_to_create:
        unique_creates = []
        seen_create_urls = set()
        for r in records_to_create:
            if r.property_url and r.property_url not in seen_create_urls:
                seen_create_urls.add(r.property_url)
                unique_creates.append(r)
        if unique_creates:
            PropertyEvaluation.objects.bulk_create(
                unique_creates,
                batch_size=batch_size,
                ignore_conflicts=True,
            )

    if records_to_update:
        bulk_update_evaluation_records(records_to_update, property_type, batch_size)

    return chunk_passed, chunk_duplicates
