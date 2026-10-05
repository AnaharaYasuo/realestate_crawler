"""ML 特徴量アライメントとアンサンブル演算 (Issue #714)"""

import logging
from typing import Any
import numpy as np
import pandas as pd


_FEATURE_NAMES_CACHE: dict[int, list[str]] = {}


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
    """DataFrame の列順および不足列をモデルの期待入力に合わせて整列"""
    expected_features = extract_expected_feature_names(model)
    if not expected_features:
        logging.warning("ML: Could not extract feature names from model. Using DataFrame columns as is.")
        return df

    missing = [c for c in expected_features if c not in df.columns]
    if missing:
        df_aligned = df.copy()
        for col in missing:
            df_aligned[col] = 0.0
        return df_aligned[expected_features]
    return df[expected_features]


def apply_smearing_and_ensemble(
    preds_log_dict: dict[str, np.ndarray],
    weights: dict[str, float],
    smearing_factor: float,
    areas: np.ndarray,
) -> np.ndarray:
    """対数予測値に対しスミアリング補正と重み付きアンサンブルを適用して金額配列を算出"""
    total_weight = sum(weights.get(algo, 0.0) for algo in preds_log_dict.keys())
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
