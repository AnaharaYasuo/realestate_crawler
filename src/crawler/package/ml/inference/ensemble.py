"""ML 特徴量アライメントとアンサンブル演算・予測区間算出 (Issue #714, #1151)"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_FEATURE_NAMES_CACHE: dict[int, list[str]] = {}
DEFAULT_P10_Z_SCORE = 1.2816
BASE_LOG_UNCERTAINTY = 0.05


def _extract_from_booster(model: Any) -> list[str] | None:
    booster = getattr(model, "booster_", None)
    if booster is not None:
        bfn = getattr(booster, "feature_name", None)
        if callable(bfn):
            try:
                res = bfn()
                if isinstance(res, (list, tuple)):
                    return list(res)
            except Exception:
                pass
    get_booster = getattr(model, "get_booster", None)
    if callable(get_booster):
        try:
            b_obj = get_booster()
            b_names = getattr(b_obj, "feature_names", None)
            if b_names is not None:
                return list(b_names)
        except Exception:
            pass
    return None


def extract_expected_feature_names(model: Any) -> list[str] | None:
    """モデルから期待される特徴量列名を抽出（モデルオブジェクト ID 単位でキャッシュ）"""
    m_id = id(model)
    if m_id in _FEATURE_NAMES_CACHE:
        return _FEATURE_NAMES_CACHE[m_id]

    for attr in ("feature_names_in_", "feature_names_", "feature_name_", "feature_names"):
        val = getattr(model, attr, None)
        if val is not None:
            try:
                names = list(val)
                _FEATURE_NAMES_CACHE[m_id] = names
                return names
            except Exception:
                pass
    fn = getattr(model, "feature_name", None)
    if callable(fn):
        try:
            res = fn()
            if isinstance(res, (list, tuple)):
                names = list(res)
                _FEATURE_NAMES_CACHE[m_id] = names
                return names
        except Exception:
            pass

    from_b = _extract_from_booster(model)
    if from_b is not None:
        _FEATURE_NAMES_CACHE[m_id] = from_b
        return from_b

    return None


def align_features(df: pd.DataFrame, model: Any) -> pd.DataFrame:
    """DataFrame の列順および不足列をモデルの期待入力に合わせて整列 (copy() を排除し reindex を活用)"""
    expected_features = extract_expected_feature_names(model)
    if not expected_features:
        logger.warning("ML: Could not extract feature names from model. Using DataFrame columns as is.")
        return df

    return df.reindex(columns=expected_features, fill_value=0.0)


def apply_smearing_and_ensemble(
    preds_log_dict: dict[str, np.ndarray],
    weights: dict[str, float],
    smearing_factor: float,
    areas: np.ndarray,
) -> np.ndarray:
    """対数予測値に対しスミアリング補正と重み付きアンサンブルを適用して金額配列を算出"""
    total_weight = sum(weights.get(algo, 0.0) for algo in preds_log_dict)
    if total_weight <= 0:
        total_weight = 1.0

    num_samples = len(areas)
    ensemble_pred_units = np.zeros(num_samples, dtype=float)

    for algo, preds_log in preds_log_dict.items():
        w = weights.get(algo, 0.0) / total_weight
        if w > 0:
            pred_units = np.expm1(preds_log)
            pred_units = np.maximum(pred_units, 0.0)
            ensemble_pred_units += pred_units * w

    s_factor = float(smearing_factor) if smearing_factor and smearing_factor > 0 else 1.0
    final_preds = ensemble_pred_units * s_factor * np.array(areas, dtype=float)
    return np.maximum(final_preds, 0.0)


def compute_prediction_interval_p10(
    preds_log_dict: dict[str, np.ndarray],
    weights: dict[str, float],
    smearing_factor: float,
    areas: np.ndarray,
    z_p10: float = DEFAULT_P10_Z_SCORE,
) -> tuple[np.ndarray, np.ndarray]:
    """アンサンブルのモデル間分散から点予測値と下限10%予測値 (P10) を同時算出する"""
    point_preds = apply_smearing_and_ensemble(preds_log_dict, weights, smearing_factor, areas)
    num_samples = len(areas)
    if num_samples == 0 or not preds_log_dict:
        return point_preds, point_preds.copy()

    total_weight = sum(weights.get(algo, 0.0) for algo in preds_log_dict)
    if total_weight <= 0:
        total_weight = 1.0

    mean_log = np.zeros(num_samples, dtype=float)
    for algo, preds_log in preds_log_dict.items():
        w = weights.get(algo, 0.0) / total_weight
        if w > 0:
            mean_log += np.asarray(preds_log, dtype=float) * w

    var_log = np.zeros(num_samples, dtype=float)
    for algo, preds_log in preds_log_dict.items():
        w = weights.get(algo, 0.0) / total_weight
        if w > 0:
            diff = np.asarray(preds_log, dtype=float) - mean_log
            var_log += w * (diff ** 2)

    sigma_log = np.sqrt(var_log + (BASE_LOG_UNCERTAINTY ** 2))
    p10_preds = point_preds * np.exp(-float(z_p10) * sigma_log)
    return point_preds, np.maximum(p10_preds, 0.0)


def compute_risk_adjusted_bargain_score(
    actual_price: float | np.ndarray,
    predicted_price: float | np.ndarray,
    p10_price: float | np.ndarray,
) -> float | np.ndarray:
    """下限予測値 P10 に基づくリスク調整済みお宝割安スコア (0.0〜1.0) を算出する"""
    actual_arr = np.asarray(actual_price, dtype=float)
    pred_arr = np.asarray(predicted_price, dtype=float)
    p10_arr = np.minimum(pred_arr, np.asarray(p10_price, dtype=float))

    safe_denom = np.where(p10_arr > 0, p10_arr, 1.0)
    raw_discount = np.where(p10_arr > actual_arr, (p10_arr - actual_arr) / safe_denom, 0.0)
    clamped = np.clip(raw_discount, 0.0, 1.0)
    if np.ndim(actual_price) == 0 and np.ndim(predicted_price) == 0 and np.ndim(p10_price) == 0:
        return float(clamped)
    return clamped
