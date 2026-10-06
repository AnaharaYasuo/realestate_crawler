"""
機械学習 評価指標モジュール (Issue #715)
"""

import numpy as np


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error (MAPE) をパーセント値で算出"""
    yt = np.array(y_true, dtype=float)
    yp = np.array(y_pred, dtype=float)
    yt = np.where(yt == 0, 1.0, yt)
    return float(np.mean(np.abs((yt - yp) / yt)) * 100.0)
