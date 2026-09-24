# -*- coding: utf-8 -*-
"""
評価済み4.5万件に対する高速・ベクトル化再推論バッチスクリプト
既存の PropertyEvaluation レコードを対象に、新モデルによる予測価格を一括再計算・更新します。
"""
import os
import sys
import time
import shutil
import logging
from django.apps import apps

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import PropertyEvaluation
from package.ml.predict import bulk_predict_first_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def fast_reevaluate():
    logging.info("🚀 Starting Fast Vectorized Re-evaluation on PropertyEvaluation records...")
    t0 = time.time()
    
    app_config = apps.get_app_config("package")
    models_by_name = {m.__name__.lower(): m for m in app_config.get_models()}
    
    # 評価済みレコードを全件取得
    eval_qs = list(PropertyEvaluation.objects.filter(first_stage_predicted_price__isnull=False))
    total_evals = len(eval_qs)
    logging.info(f"Target evaluations to re-score: {total_evals:,}")
    
    # (company, property_type) ごとにグループ化
    grouped = {}
    for ev in eval_qs:
        key = f"{ev.company}{ev.property_type}".lower()
        grouped.setdefault(key, []).append(ev)
        
    total_updated = 0
    BATCH_SIZE = 500
    
    for key, ev_list in grouped.items():
        model_class = models_by_name.get(key)
        if not model_class:
            logging.warning(f"Model class not found for {key} ({len(ev_list)} records), skipping.")
            continue
            
        logging.info(f"Processing {model_class.__name__} ({len(ev_list):,} records)...")
        
        # モデルオブジェクトをURLでマッピング
        if hasattr(model_class, "pageUrl"):
            url_field = "pageUrl"
        elif hasattr(model_class, "url"):
            url_field = "url"
        else:
            url_field = None
        if not url_field:
            field_names = [f.name for f in model_class._meta.get_fields()]
            if "pageUrl" in field_names:
                url_field = "pageUrl"
            elif "url" in field_names:
                url_field = "url"
            else:
                url_field = None
            
        if not url_field:
            logging.warning(f"No URL field found on {model_class.__name__}")
            continue
            
        urls = [e.property_url for e in ev_list if e.property_url]
        raw_items = model_class.objects.filter(**{f"{url_field}__in": urls})
        item_map = {getattr(item, url_field): item for item in raw_items}
        
        paired = []
        for e in ev_list:
            item = item_map.get(e.property_url)
            if item:
                paired.append((e, item))
                
        # 500件単位で一括推論 & 一括更新
        for i in range(0, len(paired), BATCH_SIZE):
            chunk = paired[i:i + BATCH_SIZE]
            chunk_evs = [p[0] for p in chunk]
            chunk_items = [p[1] for p in chunk]
            
            # ベクトル化高速推論
            pred_prices = bulk_predict_first_stage(chunk_items)
            
            for ev, item, pred_p in zip(chunk_evs, chunk_items, pred_prices):
                ev.first_stage_predicted_price = pred_p
                ask_p = float(item.price) / 10000.0 if getattr(item, "price", None) else 0.0
                ev.is_first_stage_passed = (pred_p > 0 and ask_p > 0 and pred_p >= ask_p)
                
            PropertyEvaluation.objects.bulk_update(chunk_evs, ["first_stage_predicted_price", "is_first_stage_passed"], batch_size=BATCH_SIZE)
            total_updated += len(chunk)
            
        logging.info(f"  Updated {model_class.__name__}: {len(paired):,} records. (Total updated: {total_updated:,}/{total_evals:,})")
        sys.stdout.flush()
        
    elapsed = time.time() - t0
    logging.info(f"✅ Fast Re-evaluation Completed in {elapsed:.1f}s! Total updated: {total_updated:,}")
    
    # 残差分布の自動再分析を実行
    logging.info("📊 Running updated distribution analysis...")
    from scripts.debug_tools.analyze_prediction_distribution import analyze
    analyze()
    
    # プロット画像をアーティファクトへコピー
    src_png = "/app/prediction_residuals_distribution.png"
    if not os.path.exists(src_png):
        src_png = os.path.join(_scripts_dir, "debug_tools", "prediction_residuals_distribution.png")
    dst_png = r"C:\Users\weare\.gemini\antigravity-ide\brain\6a365ac0-43d7-401e-aac6-d49373a5663f\prediction_residuals_distribution.png"
    if os.path.exists(src_png):
        try:
            shutil.copy2(src_png, dst_png)
            logging.info(f"✔ Copied updated plot to artifact: {dst_png}")
        except Exception as e:
            logging.warning(f"Could not copy plot directly: {e}")

if __name__ == "__main__":
    fast_reevaluate()
