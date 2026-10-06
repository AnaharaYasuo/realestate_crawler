"""
アンサンブル学習および評価モジュール (Issue #715)
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
from sklearn.model_selection import KFold, RepeatedKFold

logger = logging.getLogger(__name__)


class TrainedEnsemble(dict):
    """学習済みアンサンブルモデル構造体"""

    def __init__(self, models: dict[str, Any], weights: dict[str, float] | None = None, smearing_factor: float = 1.0):
        super().__init__(models)
        self.weights = weights or {}
        self.smearing_factor = smearing_factor


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


def get_cv_strategy(df_len: int) -> tuple[Any, str]:
    """データ長に応じたクロスバリデーション戦略を返却"""
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
) -> None:
    """CV 各 Fold での評価と OOF 予測の蓄積"""
    mapes, maes, r2s = [], [], []
    for train_idx, val_idx in rkf.split(X):
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
) -> Any:
    """単一アルゴリズムのハイパーパラメータ調整・CV評価・全体学習"""
    if len(df) >= 100:
        logger.info("Tuning hyperparameters for %s...", name)
        params = tune_hyperparameters(X, y, name, sample_weight=sample_weight)
        logger.info("Best params for %s: %s", name, params)
    else:
        params = {}

    evaluate_folds(name, params, X, y, df, rkf, sample_weight, oof_preds, oof_counts)

    final_model = get_regressor(name, params)
    if sample_weight is not None:
        final_model.fit(X, y, sample_weight=sample_weight)
    else:
        final_model.fit(X, y)
    print_feature_importance(final_model, name, feature_cols)
    return final_model


def optimize_ensemble_weights(
    df: pd.DataFrame,
    oof_preds: dict[str, np.ndarray],
    oof_counts: dict[str, np.ndarray],
    algos: list[str],
) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
    """OOF 予測に基づくアンサンブル最適重みの算出"""
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
        return float(calculate_mape(y_actual, pred_price))

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


def compute_smearing_factor(df: pd.DataFrame, oof_unit_preds: np.ndarray, opt_w: np.ndarray) -> float:
    """Duan's Smearing バイアス補正係数の算出"""
    ensemble_pred_units = oof_unit_preds @ opt_w
    actual_unit_prices = df["price"].values / np.maximum(0.1, df["area"].values)
    log_residuals = np.log(np.maximum(0.1, actual_unit_prices)) - np.log(np.maximum(0.1, ensemble_pred_units))
    if len(log_residuals) >= 10:
        low = np.percentile(log_residuals, 2)
        high = np.percentile(log_residuals, 98)
        clean_log_res = log_residuals[(log_residuals >= low) & (log_residuals <= high)]
    else:
        clean_log_res = log_residuals

    mean_bias = float(np.mean(clean_log_res)) if len(clean_log_res) > 0 else 0.0
    var_res = float(np.var(clean_log_res)) if len(clean_log_res) > 0 else 0.0
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
    rkf, cv_desc = get_cv_strategy(len(df))
    algos = list(ALGOS)

    logger.info("\n--- Tuning & Cross-Validating models for Stage: %s (%s) ---", stage_name, cv_desc)

    oof_preds = {name: np.zeros(len(df)) for name in algos}
    oof_counts = {name: np.zeros(len(df)) for name in algos}
    trained_models = {}
    for name in algos:
        trained_models[name] = train_single_algo(
            name, X, y, df, rkf, sample_weight, feature_cols, oof_preds, oof_counts
        )

    optimal_weights, opt_w, oof_unit_preds = optimize_ensemble_weights(df, oof_preds, oof_counts, algos)
    smearing_factor = compute_smearing_factor(df, oof_unit_preds, opt_w)

    return TrainedEnsemble(trained_models, optimal_weights, smearing_factor)
