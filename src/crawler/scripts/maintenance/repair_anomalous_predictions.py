"""
全社の予測価格乖離異常レコード（3倍超または0.33倍未満）修復スクリプト (Issue #1116)
"""
import logging
import os
import sys
import time
from typing import Any

_current_dir = os.path.dirname(os.path.abspath(__file__))
_crawler_dir = os.path.dirname(_current_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings

realestateSettings.configure()

from package.ml.investment_evaluator import evaluate_investment_property
from package.ml.predict import bulk_predict_first_stage
from package.models.evaluation import PropertyEvaluation
from scripts.ops.send_recommendations import (
    batch_resolve_properties,
    is_investment_type,
    normalize_asking_price_man,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BATCH_SIZE = 500

def find_all_anomalous_evaluation_records() -> list[tuple[Any, Any]]:
    """全社の PropertyEvaluation から売出価格と3倍超または0.33倍未満で乖離している異常レコードを走査"""
    logger.info("Scanning ALL companies for anomalous predicted prices...")
    
    # 乖離の可能性のある全レコードを走査（特に高額予測または高スコア候補）
    target_qs = list(PropertyEvaluation.objects.filter(
        first_stage_predicted_price__isnull=False
    ).exclude(first_stage_predicted_price=0))
    logger.info(f"Total evaluated records fetched: {len(target_qs):,}")
    
    prop_map = batch_resolve_properties(target_qs)
    anomalous = []
    
    for ev in target_qs:
        p = prop_map.get(ev.property_url)
        if not p or not getattr(p, "price", None):
            continue
        ask_man = normalize_asking_price_man(p.price)
        if ask_man <= 0:
            continue
        p1 = float(ev.first_stage_predicted_price or 0.0)
        ratio = p1 / ask_man
        if ratio > 3.0 or ratio < 0.33:
            anomalous.append((ev, p))
            
    logger.info(f"Found {len(anomalous):,} anomalous evaluation records across all companies.")
    return anomalous

def repair_anomalous_records(anomalous_pairs: list[tuple[Any, Any]]) -> int:
    """異常レコードを最新モデルで一括再推論・更新"""
    if not anomalous_pairs:
        logger.info("No anomalous records to repair.")
        return 0
        
    total_repaired = 0
    t0 = time.time()
    
    for i in range(0, len(anomalous_pairs), BATCH_SIZE):
        chunk = anomalous_pairs[i:i + BATCH_SIZE]
        chunk_evs = [pair[0] for pair in chunk]
        chunk_props = [pair[1] for pair in chunk]
        
        preds = bulk_predict_first_stage(chunk_props)
        
        for ev, prop, pred_price in zip(chunk_evs, chunk_props, preds):
            ev.first_stage_predicted_price = pred_price
            ask_man = normalize_asking_price_man(prop.price)
            ev.is_first_stage_passed = bool(pred_price > 0 and ask_man > 0 and pred_price >= ask_man)
            
            if is_investment_type(ev.property_type):
                evaluate_investment_property(prop, ev)
                
        update_fields = [
            "first_stage_predicted_price",
            "is_first_stage_passed",
            "total_investment_score",
            "investment_score",
            "cashflow_score",
            "finance_score",
            "estimated_sekisan_price",
            "net_operating_income",
            "debt_service",
            "cash_flow",
            "dscr",
            "coc_return",
            "sekisan_ratio",
        ]
        PropertyEvaluation.objects.bulk_update(chunk_evs, update_fields, batch_size=BATCH_SIZE)
        total_repaired += len(chunk)
        logger.info(f"Repaired {total_repaired:,} / {len(anomalous_pairs):,} records...")
        
    elapsed = time.time() - t0
    logger.info(f"✅ Successfully repaired {total_repaired:,} records in {elapsed:.1f}s.")
    return total_repaired

def main():
    anomalous_pairs = find_all_anomalous_evaluation_records()
    repair_anomalous_records(anomalous_pairs)

if __name__ == "__main__":
    main()
