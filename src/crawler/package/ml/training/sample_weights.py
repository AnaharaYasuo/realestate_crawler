"""
掲載日からの時間減衰サンプル重み算出モジュール (Issue #715)
"""

import datetime
from typing import Any

import numpy as np
import pandas as pd


def _parse_single_date_to_days(d: Any, target_base: datetime.date) -> float:
    """単一の日付値を target_base からの経過日数(float)へ変換。不正時は np.nan"""
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return np.nan
    if hasattr(d, "date") and callable(d.date):
        return max(0.0, float((target_base - d.date()).days))
    if isinstance(d, datetime.date):
        return max(0.0, float((target_base - d).days))
    if isinstance(d, (np.datetime64, pd.Timestamp)):
        try:
            dt = pd.to_datetime(d).date()
            return max(0.0, float((target_base - dt).days))
        except (ValueError, TypeError):
            return np.nan
    if isinstance(d, str):
        try:
            dt = datetime.date.fromisoformat(str(d)[:10])
            return max(0.0, float((target_base - dt).days))
        except (ValueError, TypeError):
            return np.nan
    return np.nan


def calculate_time_decay_weights(
    dates: Any,
    base_date: datetime.date | datetime.datetime | None = None,
    decay_rate: float = 0.0005,
    min_weight: float = 0.20,
    prices_man: Any = None,
) -> np.ndarray:
    """
    物件の掲載日からの経過日数に応じた時間減衰重み、および
    低価格帯の不均一分散（Heteroskedasticity: MAPEペナルティの低下）を是正する
    価格感応重みを算出して乗算する (Issue #1307)。
    """
    if base_date is None:
        target_base = datetime.datetime.now(datetime.timezone.utc).date()
    elif isinstance(base_date, datetime.datetime):
        target_base = base_date.date()
    else:
        target_base = base_date

    parsed_days = [_parse_single_date_to_days(d, target_base) for d in dates]

    days_arr = np.array(parsed_days, dtype=np.float64)
    # ベクトル化演算
    weights = np.exp(-decay_rate * days_arr)
    weights = np.maximum(min_weight, weights)
    # 不正・欠損値は min_weight に置換
    weights = np.where(np.isnan(weights), min_weight, weights)

    if prices_man is not None:
        prices_arr = np.array(prices_man, dtype=np.float64)
        valid_prices = np.where((prices_arr > 0) & (~np.isnan(prices_arr)), prices_arr, 3000.0)
        log_p = np.log(np.maximum(10.0, valid_prices))
        ref_log = float(np.log(3000.0))
        w_price = np.sqrt(ref_log / log_p)
        w_price = np.clip(w_price, 0.5, 2.0)
        weights = weights * w_price
        mean_w = np.mean(weights)
        if mean_w > 0:
            weights = weights / mean_w

    return weights.astype(np.float64)
