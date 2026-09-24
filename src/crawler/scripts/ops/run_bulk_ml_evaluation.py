# ruff: noqa: E402
"""
バルクML評価バッチスクリプト (Option B)

クローリングによって保存された未評価物件に対して、
MLモデルをメモリ上に一度だけロードし、一括で一次・二次理論価格評価および投資評価を実行します。
"""
import os
import sys
import logging

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import close_old_connections
from package.models.evaluation import PropertyEvaluation
from package.ml.predict import bulk_predict_first_stage
from package.ml.investment_evaluator import evaluate_investment_property
from package.utils.converter import parse_chidai
from package.utils.deduplication import find_duplicate_property
from package.utils.text_risk_analyzer import analyze_text_risks
from django.apps import apps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORTAL_COMPANIES = ["athome", "homes"]
COMPANIES = ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]

def get_all_property_models(skip_portals=False):
    """登録されている全物件モデルを取得"""
    property_models = []
    target_companies = [c for c in COMPANIES if not (skip_portals and c in PORTAL_COMPANIES)]
    app_config = apps.get_app_config("package")
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        if any(model_name.startswith(c) for c in target_companies):
            property_models.append(model)
    return property_models


def _populate_text_risks(evaluation_record, item):
    """物件テキストからプロ目線リスクフラグを抽出し評価レコードに反映する"""
    full_text = " ".join(filter(None, [
        getattr(item, "propertyName", ""),
        getattr(item, "address", ""),
        getattr(item, "traffic", ""),
        getattr(item, "biko", ""),
        getattr(item, "tochikenri", ""),
        getattr(item, "genkyo", ""),
        getattr(item, "torihiki", ""),
        getattr(item, "setsubi", ""),
    ]))
    chikunengetsu = getattr(item, "chikunengetsu", None)
    if chikunengetsu:
        chikunengetsu_str = chikunengetsu.strftime("%Y年%m月") if hasattr(chikunengetsu, "strftime") else str(chikunengetsu)
    else:
        chikunengetsu_str = getattr(item, "chikunengetsuStr", None)
    kaisu_str = getattr(item, "kaisu", None) or getattr(item, "shozaikai", None)
    total_floors = getattr(item, "chijoKaisu", None) or getattr(item, "totalFloors", None)
    parsed_total_floors = None
    if total_floors is not None:
        try:
            parsed_total_floors = int(str(total_floors).replace("階", "").strip())
        except ValueError:
            parsed_total_floors = None
    risks = analyze_text_risks(
        full_text,
        chikunengetsu_str=chikunengetsu_str,
        kaisu_str=str(kaisu_str) if kaisu_str is not None else None,
        total_floors=parsed_total_floors,
    )
    for k, v in risks.items():
        setattr(evaluation_record, k, v)


def _resolve_company_and_type(model_name: str) -> tuple[str, str]:
    """モデル名から会社名と物件種別を判定する"""
    company = "unknown"
    for c in COMPANIES:
        if model_name.lower().startswith(c):
            company = c
            break
    property_type = model_name.lower().replace(company, "")
    return company, property_type


def _filter_unprocessed_items(model, existing_eval_map, force, limit_per_model):
    """未処理物件を走査してリスト化する"""
    unprocessed_items = []
    skipped_count = 0
    for item in model.objects.all():
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        if not page_url:
            continue
        existing_eval = existing_eval_map.get(page_url)
        if not force and existing_eval and existing_eval.first_stage_predicted_price is not None:
            skipped_count += 1
            continue
        unprocessed_items.append(item)
        if limit_per_model and len(unprocessed_items) >= limit_per_model:
            break
    return unprocessed_items, skipped_count


def _build_or_update_eval_record(item, price_stage1, existing, company, property_type):
    """単一物件の評価レコードを生成または更新する"""
    page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
    asking_price = (float(item.price) / 10000.0) if getattr(item, "price", None) else 0.0
    is_passed = bool(price_stage1 > 0 and asking_price > 0 and price_stage1 >= asking_price)

    chidai_val = getattr(item, "chidai", None)
    if chidai_val is None and getattr(item, "chidaiStr", None):
        chidai_val = parse_chidai(item.chidaiStr)
    monthly_rent = int(chidai_val) if chidai_val and int(chidai_val) > 0 else None
    liability = Decimal(int((monthly_rent * 12.0) / 10000.0 / 0.05)) if monthly_rent else None

    if existing and existing.pk:
        rec = existing
        rec.company = company
        rec.property_type = property_type
        rec.property_id = item.id
        rec.first_stage_predicted_price = price_stage1
        rec.is_first_stage_passed = is_passed
        rec.analysis_status = "pending"
        rec.monthly_land_rent = monthly_rent
        rec.land_rent_liability = liability
        _populate_text_risks(rec, item)
        is_new = False
    else:
        rec = PropertyEvaluation(
            property_url=page_url,
            company=company,
            property_type=property_type,
            property_id=item.id,
            first_stage_predicted_price=price_stage1,
            is_first_stage_passed=is_passed,
            analysis_status="pending",
            monthly_land_rent=monthly_rent,
            land_rent_liability=liability,
        )
        _populate_text_risks(rec, item)
        is_new = True

    if is_passed and not rec.duplicate_of:
        dup = find_duplicate_property(rec, new_prop=item)
        if dup:
            rec.duplicate_of = dup
            rec.is_slack_notified = True

    if "investment" in property_type or "invest" in property_type:
        rec = evaluate_investment_property(item, rec)

    return rec, is_new


def _bulk_update_evaluation_records(records_to_update, property_type, batch_size):
    """更新対象レコードの重複を除去してbulk_updateを実行する"""
    valid_updates = []
    seen_pks = set()
    for r in records_to_update:
        if r.pk and r.pk not in seen_pks:
            seen_pks.add(r.pk)
            valid_updates.append(r)

    if not valid_updates:
        return

    update_fields = [
        "company", "property_type", "property_id", "first_stage_predicted_price",
        "is_first_stage_passed", "analysis_status", "duplicate_of", "is_slack_notified",
        "monthly_land_rent", "land_rent_liability",
        "is_psychological_defect", "is_as_is_condition", "is_boundary_unspecified",
        "is_unbuildable", "is_urbanization_control_area", "has_private_road_burden",
        "is_sublease", "bath_type", "gas_type", "sewage_type",
        "has_elevator", "is_stair_only_3f_plus", "is_old_earthquake_standard",
    ]
    if "investment" in property_type or "invest" in property_type:
        update_fields.extend([
            "estimated_sekisan_price", "net_operating_income", "debt_service",
            "dscr", "total_investment_score",
        ])
    PropertyEvaluation.objects.bulk_update(
        valid_updates,
        fields=update_fields,
        batch_size=batch_size,
    )


def _process_eval_chunk(chunk, predicted_prices, existing_eval_map, company, property_type, batch_size):
    """チャンク内の物件を評価しDBに一括保存する"""
    records_to_create = []
    records_to_update = []
    for item, price_stage1 in zip(chunk, predicted_prices):
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        existing = existing_eval_map.get(page_url)
        rec, is_new = _build_or_update_eval_record(item, price_stage1, existing, company, property_type)
        if is_new:
            records_to_create.append(rec)
        else:
            records_to_update.append(rec)

    if records_to_create:
        PropertyEvaluation.objects.bulk_create(records_to_create, batch_size=batch_size)

    if records_to_update:
        _bulk_update_evaluation_records(records_to_update, property_type, batch_size)


def _evaluate_single_model(model, existing_eval_map, force, limit_per_model, batch_size=500):
    """単一モデルの物件群を評価（スレッドセーフ）"""
    close_old_connections()
    model_name = model.__name__
    company, property_type = _resolve_company_and_type(model_name)
    evaluated_count = 0
    try:
        unprocessed_items, skipped_count = _filter_unprocessed_items(
            model, existing_eval_map, force, limit_per_model
        )
        if not unprocessed_items:
            return evaluated_count, skipped_count

        for chunk_idx in range(0, len(unprocessed_items), batch_size):
            chunk = unprocessed_items[chunk_idx:chunk_idx + batch_size]
            predicted_prices = bulk_predict_first_stage(chunk)
            _process_eval_chunk(
                chunk, predicted_prices, existing_eval_map, company, property_type, batch_size
            )
            evaluated_count += len(chunk)
            logger.info("Evaluated %d properties for %s...", evaluated_count, model_name)
            sys.stdout.flush()
    finally:
        close_old_connections()

    return evaluated_count, skipped_count


def run_bulk_evaluation(force=False, limit_per_model=None, skip_portals=False):
    concurrency = int(os.getenv("BULK_EVAL_CONCURRENCY", "4"))
    logger.info(
        "🚀 Starting Bulk ML Evaluation Batch (Parallel Threads=%d, force=%s, limit=%s, skip_portals=%s)...",
        concurrency, force, limit_per_model, skip_portals,
    )

    # 1. 評価済みレコードを一括ロード (N+1解消のためのインメモリ辞書化)
    existing_eval_map = {
        e.property_url: e
        for e in PropertyEvaluation.objects.all().only(
            "id", "property_url", "first_stage_predicted_price", "second_stage_predicted_price", "is_first_stage_passed"
        )
    }

    models = get_all_property_models(skip_portals=skip_portals)
    evaluated_count = 0
    skipped_count = 0
    failed_models = []
    BATCH_SIZE = 500

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_model = {
            executor.submit(_evaluate_single_model, model, existing_eval_map, force, limit_per_model, BATCH_SIZE): model
            for model in models
        }
        for future in as_completed(future_to_model):
            m = future_to_model[future]
            try:
                cnt, skp = future.result()
                evaluated_count += cnt
                skipped_count += skp
            except Exception:  # noqa: BLE001
                failed_models.append(m.__name__)
                logger.exception("Failed evaluating %s", m.__name__)

    if failed_models:
        logger.error("❌ Bulk ML Evaluation failed on models: %s", failed_models)
        sys.exit(1)

    logger.info("✅ Bulk ML Evaluation Finished! Evaluated: %d, Skipped (Already done): %d", evaluated_count, skipped_count)
    sys.stdout.flush()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulk ML Evaluation Batch")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already evaluated properties")
    parser.add_argument("--limit", type=int, default=None, help="Limit properties per model for testing")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (athome, homes)")
    args = parser.parse_args()
    run_bulk_evaluation(force=args.force, limit_per_model=args.limit, skip_portals=args.skip_portals)
