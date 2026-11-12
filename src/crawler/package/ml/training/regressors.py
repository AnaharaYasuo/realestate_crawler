"""
学習器ファクトリおよびパラメータ定義モジュール (Issue #715)
"""

import os
from typing import Any

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor

from package.ml.training.anchor_residual import AnchorResidualEstimator

PARAM_GRIDS: dict[str, list[dict[str, Any]]] = {
    "lgb": [
        {"learning_rate": 0.05, "num_leaves": 31, "max_depth": 6, "min_child_samples": 20},
        {"learning_rate": 0.1, "num_leaves": 63, "max_depth": 8, "min_child_samples": 10},
    ],
    "xgb": [
        {"learning_rate": 0.05, "max_depth": 6, "subsample": 0.8},
        {"learning_rate": 0.1, "max_depth": 6, "subsample": 0.9},
    ],
    "cat": [
        {"learning_rate": 0.08, "depth": 6, "l2_leaf_reg": 3},
    ],
    "rf": [
        {"n_estimators": 100, "max_depth": 15, "min_samples_leaf": 5},
    ],
}


def get_regressor(name: str, params: dict[str, Any] | None = None, *, use_anchor_residual: bool = True) -> Any:
    """指定されたアルゴリズム名に対応する回帰器インスタンスを生成（既定で AnchorResidualEstimator ラップ）"""
    p = params or {}
    ml_threads = int(os.getenv("ML_NUM_THREADS", "-1"))

    if name == "lgb":
        base = lgb.LGBMRegressor(random_state=42, verbose=-1, n_jobs=ml_threads, n_estimators=100, **p)
    elif name == "xgb":
        base = xgb.XGBRegressor(random_state=42, n_jobs=ml_threads, n_estimators=100, **p)
    elif name == "cat":
        base = CatBoostRegressor(random_state=42, verbose=0, thread_count=ml_threads, iterations=200, **p)
    elif name == "rf":
        base = RandomForestRegressor(
            random_state=42,
            n_jobs=ml_threads,
            n_estimators=p.get("n_estimators", 100),
            max_depth=p.get("max_depth", None),
            min_samples_leaf=p.get("min_samples_leaf", 5),
            max_features=p.get("max_features", "sqrt"),
        )
    else:
        raise ValueError(f"Unknown algorithm: {name}")

    return AnchorResidualEstimator(base) if use_anchor_residual else base


def get_quantile_p10_regressor(alpha: float = 0.10, *, use_anchor_residual: bool = True) -> Any:
    """下限予測値 P10 用の LightGBM 分位点回帰器（Pinball Loss, alpha=0.10）を生成する。"""
    ml_threads = int(os.getenv("ML_NUM_THREADS", "-1"))
    base = lgb.LGBMRegressor(
        objective="quantile",
        alpha=float(alpha),
        random_state=42,
        verbose=-1,
        n_jobs=ml_threads,
        n_estimators=120,
        learning_rate=0.05,
        num_leaves=31,
        max_depth=6,
        min_child_samples=10,
    )
    return AnchorResidualEstimator(base) if use_anchor_residual else base
