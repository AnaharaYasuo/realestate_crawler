"""
ハイパーパラメータチューニングモジュール (Issue #715)
"""

from typing import Any

import numpy as np
import pandas as pd
from package.ml.training.metrics import calculate_mape
from package.ml.training.regressors import PARAM_GRIDS, get_regressor
from sklearn.model_selection import KFold


def tune_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    algo_name: str,
    sample_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    簡易的なハイパーパラメータグリッドサーチを行い、
    3-Fold CV で最も MAPE が良かったパラメータの辞書を返します。
    """
    if len(X) > 5000:
        tune_idx = np.random.default_rng(42).choice(len(X), size=5000, replace=False)
        x_tune = X.iloc[tune_idx].reset_index(drop=True)
        y_tune = y.iloc[tune_idx].reset_index(drop=True)
        sw_tune = sample_weight[tune_idx] if sample_weight is not None else None
    else:
        x_tune, y_tune = X.reset_index(drop=True), y.reset_index(drop=True)
        sw_tune = sample_weight if sample_weight is not None else None

    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    best_params: dict[str, Any] = {}
    best_mape = float("inf")

    param_grid = PARAM_GRIDS.get(algo_name, [{}])
    for params in param_grid:
        mapes = []
        for train_idx, val_idx in kf.split(x_tune):
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
