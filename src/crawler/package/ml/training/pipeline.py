"""
機械学習パイプライン実行オーケストレータモジュール (Issue #715, #1151)
"""

import gc
import logging
import os
import sys
import time
from typing import Any

import pandas as pd
from package.ml.constants import PROPERTY_TYPES
from package.ml.features import FEATURE_SETS
from package.ml.training.artifacts import (
    save_metadata,
    save_stage_models,
    sync_existing_metadata_from_storage,
    upload_models_to_storage,
)
from package.ml.training.cleaning import clean_training_data
from package.ml.training.data_loader import (
    collect_model_classes_by_type,
    get_evaluation_and_duplicate_caches,
    stream_training_feature_chunks,
)
from package.ml.training.dummy_data import generate_dummy_data
from package.ml.training.ensemble import train_and_compare
from package.ml.training.market_master import (
    build_market_master_from_models,
)
from package.ml.training.sample_weights import calculate_time_decay_weights
from package.utils.batch_metrics import BatchMetrics, format_batch_duration
from package.utils.newrelic_helper import _read_cpu_metrics, _read_host_memory_fallback

logger = logging.getLogger(__name__)

DEFAULT_MAX_TRAINING_ITEMS = 50000


def _downcast_chunk_columns(df: pd.DataFrame) -> pd.DataFrame:
    """単一チャンクの数値列を float32 / downcasted int に圧縮"""
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].astype("float32")
        elif pd.api.types.is_integer_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast="integer")
    return df


def _build_compact_dataframe(chunk_stream: Any) -> pd.DataFrame:
    """
    特徴量チャンクを逐次 DataFrame 化し、低精度型へ圧縮してメモリ常駐量を最小化 (Issue #1517)
    """
    dfs: list[pd.DataFrame] = []
    for chunk in chunk_stream:
        if chunk:
            dfs.append(_downcast_chunk_columns(pd.DataFrame(chunk)))
            del chunk

    if not dfs:
        return pd.DataFrame()

    full_df = pd.concat(dfs, ignore_index=True)
    del dfs
    gc.collect()

    for col in full_df.columns:
        if pd.api.types.is_object_dtype(full_df[col]) and col not in ("pageUrl", "url"):
            try:
                if full_df[col].nunique() < len(full_df) * 0.5:
                    full_df[col] = full_df[col].astype("category")
            except Exception as e:  # noqa: BLE001
                logger.debug("Skipped category downcast for column %s: %s", col, e)

    return full_df


def _chunk_single_items(first_item: Any, iterator: Any) -> Any:
    """単一要素イテレータを1000件チャンクのジェネレータに変換"""
    current_chunk = [first_item]
    for item in iterator:
        current_chunk.append(item)
        if len(current_chunk) >= 1000:
            yield current_chunk
            current_chunk = []
    if current_chunk:
        yield current_chunk


def _resolve_from_list(features_list: list[Any]) -> pd.DataFrame:
    """リスト入力からメモリ効率の良い DataFrame を解決"""
    if not features_list:
        return pd.DataFrame()
    if isinstance(features_list[0], list):
        return _build_compact_dataframe(features_list)
    return _downcast_chunk_columns(pd.DataFrame(features_list))


def _resolve_input_dataframe(features_iterator: Any) -> pd.DataFrame:
    """イテレータまたはリストからメモリ効率の良い DataFrame を解決"""
    if isinstance(features_iterator, list):
        return _resolve_from_list(features_iterator)

    if not hasattr(features_iterator, "__iter__"):
        return pd.DataFrame()

    sample = next(features_iterator, None)
    if sample is None:
        return pd.DataFrame()

    if isinstance(sample, list):
        def _rest_chunks():
            yield sample
            yield from features_iterator
        return _build_compact_dataframe(_rest_chunks())

    return _build_compact_dataframe(_chunk_single_items(sample, features_iterator))


def train_property_type(
    ptype: str,
    features_iterator: Any,
    feature_sets: dict[str, Any],
    model_dir: str,
    all_ensemble_weights: dict[str, Any],
    all_smearing_factors: dict[str, Any],
    allow_dummy_fallback: bool | None = None,
    all_location_encoders: dict[str, Any] | None = None,
    all_p10_conformal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """単一種別のデータクレンジング、一次/二次アンサンブル学習、モデル保存を実行"""
    ptype_start = time.perf_counter()
    mem_start_bytes, _, _ = _read_host_memory_fallback()
    mem_start_mb = round(mem_start_bytes / (1024 * 1024), 1)

    df = _resolve_input_dataframe(features_iterator)
    initial_count = len(df)

    logger.info("\n=========================================")
    logger.info(
        "Training models for Property Type: %s (records: %d, start RSS: %.1f MB)",
        ptype,
        initial_count,
        mem_start_mb,
    )
    logger.info("=========================================")
    sys.stdout.flush()
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
        logger.info(
            "Not enough real data for %s in DB (%d records). Generating dummy data (fallback allowed).",
            ptype,
            len(df),
        )
        df = generate_dummy_data(ptype)
        used_dummy = True

    before_clean = len(df)
    df = clean_training_data(df, ptype)
    after_clean = len(df)
    outliers_count = before_clean - after_clean

    dates = df["input_date"].values if "input_date" in df.columns else [None] * len(df)
    prices_man = df["price"].values if "price" in df.columns else None
    sample_weights = calculate_time_decay_weights(dates, prices_man=prices_man)

    # 一次モデルの訓練と保存
    first_cols = feature_sets[ptype]["first"]
    first_ensemble = train_and_compare(
        df,
        first_cols,
        f"{ptype} - First Stage (No Image)",
        sample_weight=sample_weights,
    )
    all_ensemble_weights.setdefault(ptype, {})["first"] = first_ensemble.weights
    all_smearing_factors.setdefault(ptype, {})["first"] = first_ensemble.smearing_factor
    if all_location_encoders is not None:
        all_location_encoders.setdefault(ptype, {})["first"] = (
            first_ensemble.location_encoder
        )
    if all_p10_conformal is not None:
        all_p10_conformal.setdefault(ptype, {})["first"] = (
            first_ensemble.p10_conformal_offset
        )
    save_stage_models(first_ensemble, model_dir, ptype, "first")
    del first_ensemble
    gc.collect()

    # 二次モデルの訓練と保存
    second_cols = feature_sets[ptype]["second"]
    second_ensemble = train_and_compare(
        df,
        second_cols,
        f"{ptype} - Second Stage (With Image)",
        sample_weight=sample_weights,
    )
    all_ensemble_weights.setdefault(ptype, {})["second"] = second_ensemble.weights
    all_smearing_factors.setdefault(ptype, {})["second"] = (
        second_ensemble.smearing_factor
    )
    if all_location_encoders is not None:
        all_location_encoders.setdefault(ptype, {})["second"] = (
            second_ensemble.location_encoder
        )
    if all_p10_conformal is not None:
        all_p10_conformal.setdefault(ptype, {})["second"] = (
            second_ensemble.p10_conformal_offset
        )
    save_stage_models(second_ensemble, model_dir, ptype, "second")

    duration = time.perf_counter() - ptype_start
    mem_end_bytes, _, _ = _read_host_memory_fallback()
    mem_end_mb = round(mem_end_bytes / (1024 * 1024), 1)
    cpu_metrics = _read_cpu_metrics() or {}
    proc_cpu_pct = cpu_metrics.get("cpuPercent", 0.0)
    sys_cpu_pct = cpu_metrics.get("systemCpuPercent", 0.0)

    summary = {
        "ptype": ptype,
        "input_count": initial_count,
        "valid_count": after_clean,
        "outliers_count": outliers_count,
        "duration_sec": duration,
        "used_dummy": used_dummy,
        "mem_start_mb": mem_start_mb,
        "mem_end_mb": mem_end_mb,
        "proc_cpu_pct": proc_cpu_pct,
        "sys_cpu_pct": sys_cpu_pct,
    }
    logger.info(
        "[%s] Completed in %s (Valid: %d, Filtered: %d, Dummy: %s, RSS: %.1f MB -> %.1f MB, CPU: %.1f%%)",
        ptype,
        format_batch_duration(duration),
        after_clean,
        outliers_count,
        used_dummy,
        mem_start_mb,
        mem_end_mb,
        proc_cpu_pct,
    )
    sys.stdout.flush()
    del df, second_ensemble
    gc.collect()
    return summary


def resolve_target_property_types(raw_types: list[str] | str | None) -> list[str]:
    """CLI引数、環境変数、または既定値から対象種別リストを解決"""
    if raw_types is not None:
        if isinstance(raw_types, str):
            parts = [t.strip().lower() for t in raw_types.split(",") if t.strip()]
        else:
            parts = []
            for item in raw_types:
                parts.extend([t.strip().lower() for t in item.split(",") if t.strip()])
        valid = [t for t in parts if t in PROPERTY_TYPES]
        if valid:
            return valid

    env_val = os.environ.get("ML_TRAIN_PROPERTY_TYPES", "").strip().lower()
    if env_val:
        parts = [t.strip() for t in env_val.split(",") if t.strip()]
        valid = [t for t in parts if t in PROPERTY_TYPES]
        if valid:
            return valid

    return list(PROPERTY_TYPES)


def run_training(
    target_property_types: list[str] | str | None = None,
    allow_dummy_fallback: bool | None = None,
) -> None:
    """指定物件種別のストリーミング学習、メタデータ保存、GCSアップロードを実行 (Issue #1482)"""
    types_to_train = resolve_target_property_types(target_property_types)
    logger.info("Target property types for ML training: %s", types_to_train)

    eval_map, duplicate_urls = get_evaluation_and_duplicate_caches()
    models_by_type = collect_model_classes_by_type()

    # 軽量 values_list 走査により取引事例比較マスタを事前構築
    mkt_master = build_market_master_from_models(models_by_type, duplicate_urls)

    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
    )
    os.makedirs(model_dir, exist_ok=True)

    metrics = BatchMetrics("ML Model Training")
    all_ensemble_weights: dict[str, Any] = {}
    all_smearing_factors: dict[str, Any] = {}
    all_location_encoders: dict[str, Any] = {}
    all_p10_conformal: dict[str, Any] = {}
    ptype_summaries = []
    any_dummy_used = False
    max_items = int(
        os.environ.get("ML_MAX_TRAINING_ITEMS", str(DEFAULT_MAX_TRAINING_ITEMS))
    )

    for ptype in types_to_train:
        stream = stream_training_feature_chunks(
            ptype,
            models_by_type,
            eval_map,
            duplicate_urls,
            mkt_master,
            max_items=max_items,
        )
        summary = train_property_type(
            ptype,
            stream,
            FEATURE_SETS,
            model_dir,
            all_ensemble_weights,
            all_smearing_factors,
            allow_dummy_fallback=allow_dummy_fallback,
            all_location_encoders=all_location_encoders,
            all_p10_conformal=all_p10_conformal,
        )
        if summary.get("used_dummy"):
            any_dummy_used = True
        ptype_summaries.append(summary)
        metrics.record_processed(summary.get("valid_count", 0))
        del stream
        gc.collect()

    sync_existing_metadata_from_storage(model_dir)
    save_metadata(
        model_dir,
        all_ensemble_weights,
        all_smearing_factors,
        mkt_master,
        location_encoders=all_location_encoders,
        p10_conformal=all_p10_conformal,
    )

    if any_dummy_used:
        logger.warning("Models trained with dummy fallback data. Skipping GCS upload.")
    else:
        upload_models_to_storage(model_dir)

    metrics.finish()
    custom_sections = [
        f"• {s['ptype'].upper():<10}: 有効 {s['valid_count']:,} 件 | 除外 {s['outliers_count']:,} 件 | RSS: {s.get('mem_start_mb', 0.0):.1f}MB->{s.get('mem_end_mb', 0.0):.1f}MB | CPU: {s.get('proc_cpu_pct', 0.0):.1f}% | 時間: {format_batch_duration(s['duration_sec'])}"
        for s in ptype_summaries
    ]
    logger.info(
        "\n%s",
        metrics.build_log_banner(
            title="ML Model Re-Training Batch", custom_sections=custom_sections
        ),
    )
    logger.info(
        "\nMachine learning training pipeline completed successfully for all property types!"
    )
