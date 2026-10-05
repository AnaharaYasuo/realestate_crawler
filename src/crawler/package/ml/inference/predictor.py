"""一括ベクトル化推論 (bulk_predict) およびローカル予測エンジン (Issue #714)"""

import datetime
import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from package.ml.features import FEATURE_SETS, build_features_batch
from package.ml.inference.ensemble import align_features, apply_smearing_and_ensemble
from package.ml.inference.model_registry import ModelRegistry, get_default_registry
from package.utils.property_type_detector import PropertyTypeDetector

logger = logging.getLogger(__name__)


def detect_property_type(property_obj: Any) -> str:

    """オブジェクトまたは辞書から物件種別を判定"""
    return PropertyTypeDetector.detect_from_object(property_obj)


def prepare_df_features(features_list: list[dict[str, Any]], feature_cols: list[str]) -> pd.DataFrame:
    """特徴量辞書リストから DataFrame を生成し、未定義列を 0.0 で初期化"""
    df = pd.DataFrame(features_list)
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    df = df[feature_cols].copy()
    
    # object 型列の正規化（None 等の欠損値を NaN に正規化しつつ数値化、変換不能な文字列を検出）
    for col in df.columns:
        if df[col].dtype == "object":
            converted = pd.to_numeric(df[col], errors="coerce")
            invalid_mask = df[col].notna() & converted.isna()
            if invalid_mask.any():
                invalid_val = df[col][invalid_mask].iloc[0]
                raise ValueError(
                    f"ML feature column '{col}' has invalid non-numeric value: {invalid_val!r}"
                )
            df[col] = converted
    return df


def group_properties_by_type(properties_list: list[Any]) -> dict[str, list[tuple[int, Any]]]:
    """物件リストを種別ごとにインデックス付きでグループ化"""
    grouped: dict[str, list[tuple[int, Any]]] = {}
    for idx, prop in enumerate(properties_list):
        ptype = detect_property_type(prop)
        grouped.setdefault(ptype, []).append((idx, prop))
    return grouped


def attach_image_scores(
    features_list: list[dict[str, Any]],
    sub_indices: list[int],
    interior_scores: list[float] | None,
    layout_scores: list[float] | None,
) -> None:
    """二次推論用の室内・間取りスコアを特徴量辞書に付与"""
    for i, g_idx in enumerate(sub_indices):
        int_score = interior_scores[g_idx] if interior_scores and g_idx < len(interior_scores) else 3.0
        lay_score = layout_scores[g_idx] if layout_scores and g_idx < len(layout_scores) else 3.0
        features_list[i]["interior_score"] = float(int_score) if int_score is not None else 3.0
        features_list[i]["layout_score"] = float(lay_score) if lay_score is not None else 3.0


def predict_batch_ensemble(
    models: dict[str, Any],
    weights: dict[str, float],
    smearing_factor: float,
    df: pd.DataFrame,
) -> np.ndarray:
    """アンサンブルモデルによるバッチ予測"""
    preds_log_dict = {}
    for algo, model in models.items():
        if model and weights.get(algo, 0.0) > 0:
            df_for_pred = align_features(df, model)
            pred_log = model.predict(df_for_pred)
            preds_log_dict[algo] = np.array(pred_log)
    areas = df["area"].values
    return apply_smearing_and_ensemble(preds_log_dict, weights, smearing_factor, areas)


def _resolve_models_and_master(
    reg: ModelRegistry,
    ptype: str,
    stage_key: str,
    models_provider: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """モデル辞書および市場マスタを解決"""
    if callable(models_provider):
        first_m, second_m, mkt_master = models_provider(ptype)
        return (second_m if stage_key == "second" else first_m), mkt_master
    return reg.models(ptype, stage_key), reg.market_master()


def _resolve_weights_and_smearing(
    reg: ModelRegistry,
    ptype: str,
    stage_key: str,
    dynamic_weights: dict[str, Any] | None,
    smearing_factors: dict[str, Any] | None,
) -> tuple[dict[str, float], float]:
    """重みとスミアリング係数を解決"""
    if dynamic_weights and ptype in dynamic_weights:
        weights = dynamic_weights.get(ptype, {}).get(stage_key) or reg.weights(ptype, stage_key)
    else:
        weights = reg.weights(ptype, stage_key)

    if smearing_factors and ptype in smearing_factors:
        val = smearing_factors.get(ptype, {}).get(stage_key, 1.0)
        smearing_factor = float(val) if val and float(val) > 0 else 1.0
    else:
        smearing_factor = reg.smearing(ptype, stage_key)

    return weights, smearing_factor


def bulk_predict(
    properties_list: list[Any],
    stage: str = "first",
    interior_scores: list[float] | None = None,
    layout_scores: list[float] | None = None,
    registry: ModelRegistry | None = None,
    models_provider: Any = None,
    weights_provider: Any = None,
    smearing_provider: Any = None,
) -> list[int]:
    """
    複数物件に対する一括ベクトル化推論 (一次・二次統合)
    """
    if not properties_list:
        return []

    reg = registry or get_default_registry()
    stage_key = "second" if "second" in stage.lower() else "first"
    grouped_props = group_properties_by_type(properties_list)
    final_results = [0] * len(properties_list)

    dynamic_weights = weights_provider(reg.model_dir) if callable(weights_provider) else None
    smearing_factors = smearing_provider(reg.model_dir) if callable(smearing_provider) else None

    for ptype, items in grouped_props.items():
        models, mkt_master = _resolve_models_and_master(reg, ptype, stage_key, models_provider)
        if not models:
            continue

        sub_indices = [idx for idx, _ in items]
        sub_props = [p for _, p in items]
        features_list = build_features_batch(sub_props, ptype, mkt_comparison_master=mkt_master)

        if stage_key == "second":
            attach_image_scores(features_list, sub_indices, interior_scores, layout_scores)

        feature_cols = FEATURE_SETS.get(ptype, {}).get(stage_key, [])
        df = prepare_df_features(features_list, feature_cols)

        weights, smearing_factor = _resolve_weights_and_smearing(
            reg, ptype, stage_key, dynamic_weights, smearing_factors
        )

        preds_arr = predict_batch_ensemble(models, weights, smearing_factor, df)
        for i, val in enumerate(preds_arr):
            final_results[sub_indices[i]] = int(max(0, val))

    return final_results



def log_prediction_error(
    property_obj: Any,
    property_type: str,
    predicted_price: float,
    actual_price: float,
    features: dict[str, Any] | None = None,
) -> None:
    """乖離率が +-30% 以上の予測エラー物件をログファイルにCSV出力する (自己改善サイクルの基盤)"""
    if not actual_price or float(actual_price) <= 0:
        return

    features = features or {}
    predicted_price_man = float(predicted_price)
    actual_price_val = float(actual_price)
    actual_price_man = (actual_price_val / 10000.0) if actual_price_val >= 100_000.0 else actual_price_val

    area_val = features.get("area", 0) or features.get("tochi_menseki", 0)
    if not area_val or float(area_val) <= 0:
        return

    error_ratio = (predicted_price_man - actual_price_man) / actual_price_man
    if abs(error_ratio) >= 0.3:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "prediction_errors.csv")

        def get_attr(obj: Any, name: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)

        page_url = get_attr(property_obj, "pageUrl", "") or get_attr(property_obj, "page_url", "")
        address = get_attr(property_obj, "address", "") or f"{features.get('prefecture', '')}{features.get('city', '')}"

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "timestamp": now_str,
            "property_type": property_type,
            "page_url": page_url,
            "address": address,
            "actual_price": actual_price,
            "predicted_price": predicted_price,
            "error_ratio": f"{error_ratio:.4f}",
            **{k: v for k, v in features.items() if k not in ["prefecture", "city", "station", "company", "kouzou"]},
        }

        df_row = pd.DataFrame([row])
        header = not os.path.exists(log_path)
        try:
            df_row.to_csv(log_path, mode="a", index=False, header=header, encoding="utf-8-sig")
            logger.info("ML: Logged prediction error for %s (Error: %.1f%%)", page_url, error_ratio * 100)
        except Exception:
            logger.exception("ML: Failed to write prediction error log")


