"""
基準単価（アンカー対数㎡単価）からの残差を学習・推論するラッパー回帰器 (Issue #1360)

目的変数 `y = log1p(price / area)` に対し、`anchor_col` (`anchor_log_unit_price`) が
入力 DataFrame に存在する場合は `r = y - X[anchor_col]` を基底回帰器に学習させ、
推論時に `y_hat = X[anchor_col] + r_hat` として `log1p(unit_price)` スケールで返却する。
これにより全国300倍以上の地域単価レンジを直交分離し、決定木の分割容量を
個別画地補正（角地・間口・整形度・固定費・駅距離等）の学習へ集中させる。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


class AnchorResidualEstimator:
    """基底回帰器をラップし、アンカー対数単価からの残差学習を行う Estimator。"""

    def __init__(
        self,
        base_estimator: Any,
        anchor_col: str = "anchor_log_unit_price",
        residual_clip: float = 3.5,
    ) -> None:
        self.base_estimator = base_estimator
        self.anchor_col = anchor_col
        self.residual_clip = float(residual_clip)
        self.feature_names_in_: np.ndarray | None = None
        self._use_anchor: bool = False

    def _extract_anchor(self, X: pd.DataFrame | np.ndarray) -> np.ndarray | None:
        if isinstance(X, pd.DataFrame) and self.anchor_col in X.columns:
            arr = pd.to_numeric(X[self.anchor_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            return arr
        if self.feature_names_in_ is not None and isinstance(X, np.ndarray):
            cols = list(self.feature_names_in_)
            if self.anchor_col in cols:
                idx = cols.index(self.anchor_col)
                return np.nan_to_num(np.asarray(X[:, idx], dtype=float), nan=0.0)
        return None

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray, **fit_kwargs: Any) -> AnchorResidualEstimator:
        if isinstance(X, pd.DataFrame):
            self.feature_names_in_ = np.array(list(X.columns), dtype=object)

        y_arr = np.asarray(y, dtype=float)
        anchor = self._extract_anchor(X)
        if anchor is not None and np.any(np.abs(anchor) > 1e-6):
            self._use_anchor = True
            target = np.clip(y_arr - anchor, -self.residual_clip, self.residual_clip)
        else:
            self._use_anchor = False
            target = y_arr

        if fit_kwargs.get("sample_weight") is None:
            fit_kwargs.pop("sample_weight", None)

        try:
            self.base_estimator.fit(X, target, **fit_kwargs)
        except TypeError:
            fit_kwargs.pop("sample_weight", None)
            self.base_estimator.fit(X, target, **fit_kwargs)
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        raw_pred = np.asarray(self.base_estimator.predict(X), dtype=float)
        if not self._use_anchor:
            return np.maximum(0.0, raw_pred)
        anchor = self._extract_anchor(X)
        if anchor is None:
            return np.maximum(0.0, raw_pred)
        return np.maximum(0.0, anchor + raw_pred)

    @property
    def n_jobs(self) -> Any:
        return getattr(self.base_estimator, "n_jobs", None)

    @property
    def feature_importances_(self) -> np.ndarray:
        return np.asarray(self.base_estimator.feature_importances_)

    def get_feature_importance(self, *args: Any, **kwargs: Any) -> Any:
        return self.base_estimator.get_feature_importance(*args, **kwargs)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        params = {
            "base_estimator": self.base_estimator,
            "anchor_col": self.anchor_col,
            "residual_clip": self.residual_clip,
        }
        if deep and hasattr(self.base_estimator, "get_params"):
            for k, v in self.base_estimator.get_params(deep=True).items():
                params[f"base_estimator__{k}"] = v
        return params

    def set_params(self, **params: Any) -> AnchorResidualEstimator:
        own_keys = {"base_estimator", "anchor_col", "residual_clip"}
        delegated: dict[str, Any] = {}
        for k, v in params.items():
            if k in own_keys:
                setattr(self, k, v)
            elif k.startswith("base_estimator__"):
                delegated[k.split("__", 1)[1]] = v
            else:
                delegated[k] = v
        if delegated and hasattr(self.base_estimator, "set_params"):
            self.base_estimator.set_params(**delegated)
        return self
