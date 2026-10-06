"""
機械学習パイプライン実行オーケストレータモジュール (Issue #715)
"""

import gc
import logging
import os
import time
from typing import Any

import pandas as pd
from package.ml.constants import PROPERTY_TYPES
from package.ml.features import FEATURE_SETS
from package.ml.training.artifacts import (
    save_metadata,
    save_stage_models,
    upload_models_to_storage,
)
from package.ml.training.cleaning import clean_training_data
from package.ml.training.data_loader import (
    collect_model_classes_by_type,
    get_evaluation_and_duplicate_caches,
    stream_training_features,
)
from package.ml.training.dummy_data import generate_dummy_data
from package.ml.training.ensemble import train_and_compare
from package.ml.training.market_master import (
    build_market_master_from_models,
)
from package.ml.training.sample_weights import calculate_time_decay_weights
from package.utils.batch_metrics import BatchMetrics, format_batch_duration

logger = logging.getLogger(__name__)


def train_property_type(
    ptype: str,
    features_iterator: Any,
    feature_sets: dict[str, Any],
    model_dir: str,
    all_ensemble_weights: dict[str, Any],
    all_smearing_factors: dict[str, Any],
    allow_dummy_fallback: bool | None = None,
) -> dict[str, Any]:
    """単一種別のデータクレンジング、一次/二次アンサンブル学習、モデル保存を実行"""
    ptype_start = time.perf_counter()

    records = list(features_iterator)
    initial_count = len(records)

    logger.info("\n=========================================")
    logger.info("Training models for Property Type: %s (records: %d)", ptype, initial_count)
    logger.info("=========================================")

    df = pd.DataFrame(records) if records else pd.DataFrame()
    used_dummy = False
    if len(df) < 10:
        allow_fallback = (
            allow_dummy_fallback
            if allow_dummy_fallback is not None
            else os.environ.get("ALLOW_DUMMY_DATA", "").lower() in ("1", "true", "yes")
        )
        if not allow_fallback:
            raise RuntimeError(
                f"Insufficient real training data for property type '{ptype}' (found {len(df)} records). "
                "Dummy data generation is disallowed in production mode."
            )
        logger.info("Not enough real data for %s in DB (%d records). Generating dummy data (fallback allowed).", ptype, len(df))
        df = generate_dummy_data(ptype)
        used_dummy = True

    before_clean = len(df)
    df = clean_training_data(df, ptype)
    after_clean = len(df)
    outliers_count = before_clean - after_clean

    dates = df["input_date"].values if "input_date" in df.columns else [None] * len(df)
    sample_weights = calculate_time_decay_weights(dates)

    # 一次モデルの訓練と保存
    first_cols = feature_sets[ptype]["first"]
    first_ensemble = train_and_compare(
        df, first_cols, f"{ptype} - First Stage (No Image)", sample_weight=sample_weights
    )
    all_ensemble_weights.setdefault(ptype, {})["first"] = first_ensemble.weights
    all_smearing_factors.setdefault(ptype, {})["first"] = first_ensemble.smearing_factor
    save_stage_models(first_ensemble, model_dir, ptype, "first")

    # 二次モデルの訓練と保存
    second_cols = feature_sets[ptype]["second"]
    second_ensemble = train_and_compare(
        df, second_cols, f"{ptype} - Second Stage (With Image)", sample_weight=sample_weights
    )
    all_ensemble_weights.setdefault(ptype, {})["second"] = second_ensemble.weights
    all_smearing_factors.setdefault(ptype, {})["second"] = second_ensemble.smearing_factor
    save_stage_models(second_ensemble, model_dir, ptype, "second")

    duration = time.perf_counter() - ptype_start
    summary = {
        "ptype": ptype,
        "input_count": initial_count,
        "valid_count": after_clean,
        "outliers_count": outliers_count,
        "duration_sec": duration,
        "used_dummy": used_dummy,
    }
    logger.info(
        "[%s] Completed in %s (Valid: %d, Filtered: %d, Dummy: %s)",
        ptype,
        format_batch_duration(duration),
        after_clean,
        outliers_count,
        used_dummy,
    )
    del df, records, first_ensemble, second_ensemble
    return summary


def run_training(allow_dummy_fallback: bool | None = None) -> None:
    """全物件種別のストリーミング学習、メタデータ保存、GCSアップロードを実行"""
    eval_map, duplicate_urls = get_evaluation_and_duplicate_caches()
    models_by_type = collect_model_classes_by_type()

    # 軽量 values_list 走査により取引事例比較マスタを事前構築
    mkt_master = build_market_master_from_models(models_by_type, duplicate_urls)

    model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    os.makedirs(model_dir, exist_ok=True)

    metrics = BatchMetrics("ML Model Training")
    all_ensemble_weights: dict[str, Any] = {}
    all_smearing_factors: dict[str, Any] = {}
    ptype_summaries = []
    any_dummy_used = False

    for ptype in PROPERTY_TYPES:
        stream = stream_training_features(
            ptype,
            models_by_type,
            eval_map,
            duplicate_urls,
            mkt_master,
            max_items=15000,
        )
        summary = train_property_type(
            ptype,
            stream,
            FEATURE_SETS,
            model_dir,
            all_ensemble_weights,
            all_smearing_factors,
            allow_dummy_fallback=allow_dummy_fallback,
        )
        if summary.get("used_dummy"):
            any_dummy_used = True
        ptype_summaries.append(summary)
        metrics.record_processed(summary.get("valid_count", 0))
        gc.collect()

    save_metadata(model_dir, all_ensemble_weights, all_smearing_factors, mkt_master)

    if any_dummy_used:
        logger.warning("Models trained with dummy fallback data. Skipping GCS upload.")
    else:
        upload_models_to_storage(model_dir)

    metrics.finish()
    custom_sections = [
        f"• {s['ptype'].upper():<10}: 有効学習 {s['valid_count']:,} 件 | 除外 {s['outliers_count']:,} 件 | 所要時間: {format_batch_duration(s['duration_sec'])}"
        for s in ptype_summaries
    ]
    logger.info("\n%s", metrics.build_log_banner(title="ML Model Re-Training Batch", custom_sections=custom_sections))
    logger.info("\nMachine learning training pipeline completed successfully for all property types!")
