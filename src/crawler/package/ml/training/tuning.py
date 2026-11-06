"""
ハイパーパラメータチューニングモジュール (Issue #715)
"""

from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pandas as pd
from package.ml.training.metrics import calculate_mape
from package.ml.training.regressors import PARAM_GRIDS, get_regressor
from sklearn.model_selection import GroupKFold, KFold

MAX_TUNE_ROWS = 5000
MIN_GROUPS_FOR_GROUP_KFOLD = 3


def _subsample_for_tuning(
    X: pd.DataFrame,
    y: pd.Series,
    sample_weight: np.ndarray | None,
    groups: np.ndarray | None,
) -> tuple[pd.DataFrame, pd.Series, np.ndarray | None, np.ndarray | None]:
    """チューニング用に最大 MAX_TUNE_ROWS 件へ間引く（X/y/重み/グループを同一インデックスで抽出）"""
    g_all = np.asarray(groups) if groups is not None else None
    if len(X) > MAX_TUNE_ROWS:
        idx = np.random.default_rng(42).choice(len(X), size=MAX_TUNE_ROWS, replace=False)
        return (
            X.iloc[idx].reset_index(drop=True),
            y.iloc[idx].reset_index(drop=True),
            sample_weight[idx] if sample_weight is not None else None,
            g_all[idx] if g_all is not None else None,
        )
    return X.reset_index(drop=True), y.reset_index(drop=True), sample_weight, g_all


def _make_split_factory(
    x: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray | None,
) -> Callable[[], Iterator[tuple[np.ndarray, np.ndarray]]]:
    """groups が十分あれば GroupKFold、無ければ KFold の分割イテレータ生成関数を返す (Issue #1278)"""
    if groups is not None and len(groups) == len(x) and len(pd.unique(groups)) >= MIN_GROUPS_FOR_GROUP_KFOLD:
        gkf = GroupKFold(n_splits=3)
        return lambda: gkf.split(x, y, groups)
    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    return lambda: kf.split(x)


def _cv_mape(
    params: dict[str, Any],
    algo_name: str,
    x: pd.DataFrame,
    y: pd.Series,
    sw: np.ndarray | None,
    split_factory: Callable[[], Iterator[tuple[np.ndarray, np.ndarray]]],
) -> float:
    """指定パラメータの CV 平均 MAPE を算出"""
    mapes = []
    for train_idx, val_idx in split_factory():
        x_train, x_val = x.iloc[train_idx], x.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        model = get_regressor(algo_name, params)
        if sw is not None:
            model.fit(x_train, y_train, sample_weight=sw[train_idx])
        else:
            model.fit(x_train, y_train)
        preds_log = model.predict(x_val)
        val_areas = x_val["area"].values
        mapes.append(calculate_mape(np.expm1(y_val) * val_areas, np.expm1(preds_log) * val_areas))
    return float(np.mean(mapes))


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
    x_tune, y_tune, sw_tune, g_tune = _subsample_for_tuning(X, y, sample_weight, groups)
    split_factory = _make_split_factory(x_tune, y_tune, g_tune)

    best_params: dict[str, Any] = {}
    best_mape = float("inf")
    for params in PARAM_GRIDS.get(algo_name, [{}]):
        avg_mape = _cv_mape(params, algo_name, x_tune, y_tune, sw_tune, split_factory)
        if avg_mape < best_mape:
            best_mape = avg_mape
            best_params = params
    return best_params
