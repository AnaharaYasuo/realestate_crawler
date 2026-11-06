"""
ハイパーパラメータチューニングモジュール (Issue #715)
"""

from typing import Any

import numpy as np
import pandas as pd
from package.ml.training.metrics import calculate_mape
from package.ml.training.regressors import PARAM_GRIDS, get_regressor
from sklearn.model_selection import GroupKFold, KFold


def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    algo_name: str,
    sample_weight: np.ndarray | None = None,
    groups: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    簡易的なハイパーパラメータグリッドサーチを行い、
    3-Fold CV で最も MAPE が良かったパラメータの辞書を返します。
    groups が与えられ、かつ 3 グループ以上ある場合は GroupKFold を用い、
    評価 CV（evaluate_folds）と同一のリーク防止基準で選択します (Issue #1278)。
    """
    g_tune: np.ndarray | None = None
    if len(X) > 5000:
        tune_idx = np.random.default_rng(42).choice(len(X), size=5000, replace=False)
        x_tune = X.iloc[tune_idx].reset_index(drop=True)
        y_tune = y.iloc[tune_idx].reset_index(drop=True)
        sw_tune = sample_weight[tune_idx] if sample_weight is not None else None
        g_tune = np.asarray(groups)[tune_idx] if groups is not None else None
    else:
        x_tune, y_tune = X.reset_index(drop=True), y.reset_index(drop=True)
        sw_tune = sample_weight if sample_weight is not None else None
        g_tune = np.asarray(groups) if groups is not None else None

    if g_tune is not None and len(g_tune) == len(x_tune) and len(pd.unique(g_tune)) >= 3:
        kf: Any = GroupKFold(n_splits=3)
        split_iter_factory = lambda: kf.split(x_tune, y_tune, g_tune)  # noqa: E731
    else:
        kf = KFold(n_splits=3, shuffle=True, random_state=42)
        split_iter_factory = lambda: kf.split(x_tune)  # noqa: E731
    best_params: dict[str, Any] = {}
    best_mape = float("inf")

    param_grid = PARAM_GRIDS.get(algo_name, [{}])
    for params in param_grid:
        mapes = []
        for train_idx, val_idx in split_iter_factory():
            x_train, x_val = x_tune.iloc[train_idx], x_tune.iloc[val_idx]
            y_train, y_val = y_tune.iloc[train_idx], y_tune.iloc[val_idx]

            model = get_regressor(algo_name, params)
            if sw_tune is not None:
                sw_train = sw_tune[train_idx]
                model.fit(x_train, y_train, sample_weight=sw_train)
            else:
                model.fit(x_train, y_train)
            preds_log = model.predict(x_val)
            val_areas = x_val["area"].values
            mapes.append(calculate_mape(np.expm1(y_val) * val_areas, np.expm1(preds_log) * val_areas))

        avg_mape = float(np.mean(mapes))
        if avg_mape < best_mape:
            best_mape = avg_mape
            best_params = params

    return best_params
