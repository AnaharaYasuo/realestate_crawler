# -*- coding: utf-8 -*-
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




from package.models.evaluation import PropertyEvaluation
from package.ml.predict import bulk_predict_first_stage
from package.ml.investment_evaluator import evaluate_investment_property
from package.utils.deduplication import find_duplicate_property
from django.apps import apps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def run_bulk_evaluation(force=False, limit_per_model=None, skip_portals=False):
    logging.info(f"🚀 Starting Bulk ML Evaluation Batch (Vectorized & Bulk-Optimized, force={force}, limit={limit_per_model}, skip_portals={skip_portals})...")
    
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
    BATCH_SIZE = 500
    
    for model in models:
        model_name = model.__name__
        company = "unknown"
        for c in COMPANIES:
            if model_name.lower().startswith(c):
                company = c
                break
        property_type = model_name.lower().replace(company, "")
        
        # 未評価または未完了物件を収集
        unprocessed_items = []
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
            
        if not unprocessed_items:
            continue
            
        # チャンクごとにバッチ推論 & 一括永続化
        for chunk_idx in range(0, len(unprocessed_items), BATCH_SIZE):
            chunk = unprocessed_items[chunk_idx:chunk_idx + BATCH_SIZE]
            
            # ベクトル化一括推論 (HTTP API不要・メモリ直接推論)
            predicted_prices = bulk_predict_first_stage(chunk)
            
            records_to_create = []
            records_to_update = []
            chunk_records = []
            
            for item, price_stage1 in zip(chunk, predicted_prices):
                page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
                asking_price = (float(item.price) / 10000.0) if getattr(item, "price", None) else 0.0
                
                is_passed = False
                if price_stage1 > 0 and asking_price > 0 and price_stage1 >= asking_price:
                    is_passed = True
                    
                existing = existing_eval_map.get(page_url)
                if existing and existing.pk:
                    existing.company = company
                    existing.property_type = property_type
                    existing.property_id = item.id
                    existing.first_stage_predicted_price = price_stage1
                    existing.is_first_stage_passed = is_passed
                    existing.analysis_status = "pending"
                    
                    if is_passed and not existing.duplicate_of:
                        dup = find_duplicate_property(existing, new_prop=item)
                        if dup:
                            existing.duplicate_of = dup
                            existing.is_slack_notified = True
                    if "investment" in property_type or "invest" in property_type:
                        existing = evaluate_investment_property(item, existing)
                        
                    records_to_update.append(existing)
                elif not existing:
                    rec = PropertyEvaluation(
                        property_url=page_url,
                        company=company,
                        property_type=property_type,
                        property_id=item.id,
                        first_stage_predicted_price=price_stage1,
                        is_first_stage_passed=is_passed,
                        analysis_status="pending"
                    )
                    if is_passed:
                        dup = find_duplicate_property(rec, new_prop=item)
                        if dup:
                            rec.duplicate_of = dup
                            rec.is_slack_notified = True
                    if "investment" in property_type or "invest" in property_type:
                        rec = evaluate_investment_property(item, rec)
                        
                    records_to_create.append(rec)
                    existing_eval_map[page_url] = rec
                    
            if records_to_create:
                PropertyEvaluation.objects.bulk_create(records_to_create, batch_size=500)
                        
            valid_updates = []
            seen_pks = set()
            for r in records_to_update:
                if r.pk and r.pk not in seen_pks:
                    seen_pks.add(r.pk)
                    valid_updates.append(r)
                    
            if valid_updates:
                update_fields = [
                    "company", "property_type", "property_id", "first_stage_predicted_price",
                    "is_first_stage_passed", "analysis_status", "duplicate_of", "is_slack_notified"
                ]
                if "investment" in property_type or "invest" in property_type:
                    update_fields.extend([
                        "estimated_sekisan_price", "net_operating_income", "debt_service",
                        "dscr", "total_investment_score"
                    ])
                PropertyEvaluation.objects.bulk_update(
                    valid_updates,
                    fields=update_fields,
                    batch_size=500
                )
                    
            evaluated_count += len(chunk)
            logging.info(f"Evaluated {evaluated_count} properties so far ({model_name})...")
            sys.stdout.flush()

    logging.info(f"✅ Bulk ML Evaluation Finished! Evaluated: {evaluated_count}, Skipped (Already done): {skipped_count}")
    sys.stdout.flush()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulk ML Evaluation Batch")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already evaluated properties")
    parser.add_argument("--limit", type=int, default=None, help="Limit properties per model for testing")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (athome, homes)")
    args = parser.parse_args()
    run_bulk_evaluation(force=args.force, limit_per_model=args.limit, skip_portals=args.skip_portals)
