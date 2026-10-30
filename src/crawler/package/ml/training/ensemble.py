"""
アンサンブル学習および評価モジュール (Issue #715, #1151)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from package.ml.constants import ALGOS
from package.ml.training.metrics import calculate_mape
from package.ml.training.regressors import get_regressor
from package.ml.training.tuning import tune_hyperparameters
from scipy.optimize import minimize
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, RepeatedKFold

logger = logging.getLogger(__name__)

GROUP_CANDIDATE_COLS: tuple[str, ...] = (
    "building_group",
    "chome_group",
    "propertyName",
    "address",
)


class TrainedEnsemble(dict):
    """学習済みアンサンブルモデル構造体"""

    def __init__(self, models: dict[str, Any], weights: dict[str, float] | None = None, smearing_factor: float = 1.0):
        super().__init__(models)
        self.weights = weights or {}
        self.smearing_factor = smearing_factor


def _resolve_group_labels(df: pd.DataFrame) -> np.ndarray | None:
    """同一マンション棟・同一所在地によるデータリーク防止用グループラベルを抽出"""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for col in GROUP_CANDIDATE_COLS:
        if col in df.columns:
            vals = df[col].fillna("").astype(str).str.strip()
            non_empty = vals[vals != ""]
            if len(non_empty) == len(df) and vals.nunique() >= 2:
                return vals.to_numpy()
    if "address1" in df.columns and "address2" in df.columns:
        combined = (
            df["address1"].fillna("").astype(str).str.strip()
            + "_"
            + df["address2"].fillna("").astype(str).str.strip()
        )
        if combined.nunique() >= 2 and (combined != "_").all():
            return combined.to_numpy()
    return None


def compute_oof_chome_encoding(
    df: pd.DataFrame,
    y: pd.Series,
    cv: Any,
    groups: np.ndarray | None = None,
    smoothing: float = 10.0,
) -> np.ndarray:
    """CV Fold 内でリークなしの Empirical-Bayes 平滑化町丁目ターゲットエンコーディングを算出"""
    n = len(df)
    if n == 0:
        return np.zeros(0, dtype=np.float32)

    key_col = None
    for cand in ("chome_group", "address2", "address", "station1"):
        if cand in df.columns:
            key_col = cand
            break
    if key_col is None:
        return np.full(n, float(y.mean()), dtype=np.float32)

    keys = df[key_col].fillna("unknown").astype(str).to_numpy()
    y_arr = y.to_numpy(dtype=float)
    oof_encoded = np.zeros(n, dtype=float)
    oof_counts = np.zeros(n, dtype=float)

    split_iter = cv.split(df, y_arr, groups) if isinstance(cv, GroupKFold) and groups is not None else cv.split(df)
    for train_idx, val_idx in split_iter:
        global_mean = float(np.mean(y_arr[train_idx])) if len(train_idx) > 0 else 0.0
        train_df = pd.DataFrame({"key": keys[train_idx], "y": y_arr[train_idx]})
        stats = train_df.groupby("key")["y"].agg(["count", "mean"])
        counts = stats["count"]
        means = stats["mean"]
        smoothed = (counts * means + smoothing * global_mean) / (counts + smoothing)
        mapping = smoothed.to_dict()

        val_encoded = np.array([mapping.get(k, global_mean) for k in keys[val_idx]], dtype=float)
        oof_encoded[val_idx] += val_encoded
        oof_counts[val_idx] += 1.0

    oof_encoded /= np.maximum(1.0, oof_counts)
    return oof_encoded.astype(np.float32)


def prepare_features_and_target(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """特徴量 DataFrame と目的変数 Series の生成"""
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0

    X = df[feature_cols].copy()
    y = np.log1p(df["price"] / df["area"])
    for col in X.columns:
        if X[col].dtype == "object":
            converted = pd.to_numeric(X[col], errors="coerce")
            invalid_mask = X[col].notna() & converted.isna()
            if invalid_mask.any():
                invalid_val = X[col][invalid_mask].iloc[0]
                raise ValueError(f"ML feature column '{col}' has invalid non-numeric value: {invalid_val!r}")
            X[col] = converted.fillna(0.0)
    return X.astype(np.float32), y


def get_cv_strategy(
    df_or_len: pd.DataFrame | int,
    groups: np.ndarray | None = None,
) -> tuple[Any, str]:
    """データ長および建物・空間グループに応じたクロスバリデーション戦略を返却"""
    if isinstance(df_or_len, pd.DataFrame):
        df_len = len(df_or_len)
        if groups is None:
            groups = _resolve_group_labels(df_or_len)
    else:
        df_len = int(df_or_len)

    n_splits = 3 if df_len > 3000 else (2 if df_len < 50 else 5)
    if groups is not None and len(groups) == df_len:
        unique_groups = len( pd.unique(groups) )
        if unique_groups >= n_splits and unique_groups < df_len:
            return GroupKFold(n_splits=n_splits), f"{n_splits}-Fold Spatial/Building GroupKFold"

    if df_len > 3000:
        return KFold(n_splits=3, shuffle=True, random_state=42), "3-Fold Fast CV"
    if df_len < 50:
        return KFold(n_splits=2, shuffle=True, random_state=42), "2-Fold Quick CV"
    return RepeatedKFold(n_splits=5, n_repeats=3, random_state=42), "15-Cycle Repeated CV"


def print_feature_importance(model: Any, algo_name: str, feature_cols: list[str]) -> None:
    """学習済みモデルから特徴量重要度を集計し、上位10項目を出力"""
    try:
        if algo_name in ("lgb", "xgb", "rf"):
            importances = model.feature_importances_
        elif algo_name == "cat":
            importances = model.get_feature_importance()
        else:
            return

        feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)
        logger.info("  [%s] Feature Importance (Top 10):", algo_name)
        for name, val in feat_imp.head(10).items():
            logger.info("    - %s: %.4f", name, val)
    except Exception as e:  # noqa: BLE001
        logger.warning("  [%s] Failed to compute feature importance: %s", algo_name, e)


def evaluate_folds(
    name: str,
    params: dict[str, Any],
    X: pd.DataFrame,
    y: pd.Series,
    df: pd.DataFrame,
    rkf: Any,
    sample_weight: np.ndarray | None,
    oof_preds: dict[str, np.ndarray],
    oof_counts: dict[str, np.ndarray],
    groups: np.ndarray | None = None,
) -> None:
    """CV 各 Fold での評価と OOF 予測の蓄積"""
    mapes, maes, r2s = [], [], []
    split_iter = rkf.split(X, y, groups) if isinstance(rkf, GroupKFold) and groups is not None else rkf.split(X)
    for train_idx, val_idx in split_iter:
        x_train, x_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        fold_model = get_regressor(name, params)
        if sample_weight is not None:
            fold_model.fit(x_train, y_train, sample_weight=sample_weight[train_idx])
        else:
            fold_model.fit(x_train, y_train)
        preds_log = fold_model.predict(x_val)

        oof_preds[name][val_idx] += preds_log
        oof_counts[name][val_idx] += 1

        val_areas = df.iloc[val_idx]["area"].values
        preds_actual = np.expm1(preds_log) * val_areas
        y_val_actual = np.expm1(y_val) * val_areas

        mapes.append(calculate_mape(y_val_actual, preds_actual))
        maes.append(mean_absolute_error(y_val_actual, preds_actual))
        r2s.append(r2_score(y_val_actual, preds_actual))

    logger.info("[%s] CV Scores:", name)
    logger.info("  - MAPE: %.2f%%", float(np.mean(mapes)))
    logger.info("  - MAE:  %.2f万円", float(np.mean(maes)))
    logger.info("  - R2:   %.4f", float(np.mean(r2s)))


def train_single_algo(
    name: str,
    X: pd.DataFrame,
    y: pd.Series,
    df: pd.DataFrame,
    rkf: Any,
    sample_weight: np.ndarray | None,
    feature_cols: list[str],
    oof_preds: dict[str, np.ndarray],
    oof_counts: dict[str, np.ndarray],
    groups: np.ndarray | None = None,
) -> Any:
    """単一アルゴリズムのハイパーパラメータ調整・CV評価・全体学習"""
    if len(df) >= 100:
        logger.info("Tuning hyperparameters for %s...", name)
        params = tune_hyperparameters(X, y, name, sample_weight=sample_weight)
        logger.info("Best params for %s: %s", name, params)
    else:
        params = {}

    evaluate_folds(name, params, X, y, df, rkf, sample_weight, oof_preds, oof_counts, groups=groups)

    final_model = get_regressor(name, params)
    if sample_weight is not None:
        final_model.fit(X, y, sample_weight=sample_weight)
    else:
        final_model.fit(X, y)
    print_feature_importance(final_model, name, feature_cols)
    return final_model


def _calculate_weighted_mape(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> float:
    if sample_weight is None or len(sample_weight) != len(y_true):
        return float(calculate_mape(y_true, y_pred))
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    ape = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]) * 100.0
    w = np.maximum(1e-6, np.asarray(sample_weight[mask], dtype=float))
    return float(np.average(ape, weights=w))


def optimize_ensemble_weights(
    df: pd.DataFrame,
    oof_preds: dict[str, np.ndarray],
    oof_counts: dict[str, np.ndarray],
    algos: list[str],
    sample_weight: np.ndarray | None = None,
) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
    """OOF 予測に基づくアンサンブル最適重みの算出（時間減衰サンプル重み対応）"""
    for name in algos:
        oof_preds[name] /= np.maximum(1, oof_counts[name])

    oof_unit_preds = np.column_stack([np.maximum(0, np.expm1(oof_preds[name])) for name in algos])
    val_areas = df["area"].values
    y_actual = df["price"].values

    def objective(weights: Any) -> float:
        w = np.array(weights)
        s = np.sum(w)
        if s <= 0:
            return 9999.0
        w_norm = w / s
        pred_price = val_areas * (oof_unit_preds @ w_norm)
        return _calculate_weighted_mape(y_actual, pred_price, sample_weight=sample_weight)

    init_weights = [1.0 / len(algos)] * len(algos)
    bounds = [(0.0, 1.0)] * len(algos)
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    try:
        res = minimize(objective, init_weights, method="SLSQP", bounds=bounds, constraints=constraints)
        opt_w = res.x / np.sum(res.x) if res.success else np.array(init_weights)
    except Exception as e:  # noqa: BLE001
        logger.warning("Ensemble weight optimization fallback: %s", e)
        opt_w = np.array(init_weights)

    optimal_weights = {algos[i]: float(opt_w[i]) for i in range(len(algos))}
    logger.info("Optimized Ensemble Weights: %s", optimal_weights)
    return optimal_weights, opt_w, oof_unit_preds


def compute_smearing_factor(
    df: pd.DataFrame,
    oof_unit_preds: np.ndarray,
    opt_w: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> float:
    """Duan's Smearing バイアス補正係数の算出（時間減衰サンプル重み対応）"""
    ensemble_pred_units = oof_unit_preds @ opt_w
    actual_unit_prices = df["price"].values / np.maximum(0.1, df["area"].values)
    log_residuals = np.log(np.maximum(0.1, actual_unit_prices)) - np.log(np.maximum(0.1, ensemble_pred_units))
    weights_arr = (
        np.maximum(1e-6, np.asarray(sample_weight, dtype=float))
        if sample_weight is not None and len(sample_weight) == len(log_residuals)
        else None
    )

    if len(log_residuals) >= 10:
        low = np.percentile(log_residuals, 2)
        high = np.percentile(log_residuals, 98)
        keep_mask = (log_residuals >= low) & (log_residuals <= high)
        clean_log_res = log_residuals[keep_mask]
        clean_w = weights_arr[keep_mask] if weights_arr is not None else None
    else:
        clean_log_res = log_residuals
        clean_w = weights_arr

    if len(clean_log_res) > 0:
        if clean_w is not None and len(clean_w) == len(clean_log_res):
            mean_bias = float(np.average(clean_log_res, weights=clean_w))
            var_res = float(np.average((clean_log_res - mean_bias) ** 2, weights=clean_w))
        else:
            mean_bias = float(np.mean(clean_log_res))
            var_res = float(np.var(clean_log_res))
    else:
        mean_bias = 0.0
        var_res = 0.0

    smearing_factor = float(np.exp(mean_bias + var_res / 2.0))
    smearing_factor = max(0.90, min(1.40, smearing_factor))
    logger.info(
        "Duan's Smearing Correction Factor (mean_bias=%.4f, var=%.4f): %.4f",
        mean_bias,
        var_res,
        smearing_factor,
    )
    return smearing_factor


def train_and_compare(
    df: pd.DataFrame,
    feature_cols: list[str],
    stage_name: str,
    sample_weight: np.ndarray | None = None,
) -> TrainedEnsemble:
    """複数アルゴリズムの学習・CV比較・最適重み算出・アンサンブル構築"""
    X, y = prepare_features_and_target(df, feature_cols)
    groups = _resolve_group_labels(df)
    rkf, cv_desc = get_cv_strategy(df, groups=groups)
    algos = list(ALGOS)

    logger.info("\n--- Tuning & Cross-Validating models for Stage: %s (%s) ---", stage_name, cv_desc)

    oof_preds = {name: np.zeros(len(df)) for name in algos}
    oof_counts = {name: np.zeros(len(df)) for name in algos}
    trained_models = {}
    for name in algos:
        trained_models[name] = train_single_algo(
            name, X, y, df, rkf, sample_weight, feature_cols, oof_preds, oof_counts, groups=groups
        )

    optimal_weights, opt_w, oof_unit_preds = optimize_ensemble_weights(
        df, oof_preds, oof_counts, algos, sample_weight=sample_weight
    )
    smearing_factor = compute_smearing_factor(
        df, oof_unit_preds, opt_w, sample_weight=sample_weight
    )

    return TrainedEnsemble(trained_models, optimal_weights, smearing_factor)
