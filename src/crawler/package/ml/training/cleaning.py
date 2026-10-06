"""
学習データ クレンジングモジュール (Issue #715)
"""

import logging

import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


def _apply_iqr_filtering(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """IQR 法による外れ値除去"""
    filtered_df = df
    for col in ["price", "area"]:
        q1 = filtered_df[col].quantile(0.25)
        q3 = filtered_df[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = max(0.0, q1 - 3.5 * iqr)
        upper_bound = q3 + 3.5 * iqr
        if col == "price":
            upper_bound = max(upper_bound, 60000.0)
        elif col == "area" and ptype == "mansion":
            upper_bound = max(upper_bound, 250.0)

        pre_count = len(filtered_df)
        filtered_df = filtered_df[(filtered_df[col] >= lower_bound) & (filtered_df[col] <= upper_bound)].copy()
        post_count = len(filtered_df)
        if post_count < pre_count:
            logger.info(
                "  [IQR] Removed %d outlier records based on '%s' (Bounds: %.1f - %.1f)",
                pre_count - post_count,
                col,
                lower_bound,
                upper_bound,
            )
    return filtered_df


def _apply_isolation_forest_filtering(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """Isolation Forest による多次元外れ値除去"""
    features_for_outlier = ["price", "area", "chikunen"]
    if "tochi_menseki" in df.columns and ptype != "mansion":
        features_for_outlier.append("tochi_menseki")

    iso = IsolationForest(contamination=0.02, random_state=42)
    x_outlier = df[features_for_outlier].fillna(0)

    preds = iso.fit_predict(x_outlier)
    pre_count = len(df)
    filtered = df[preds == 1].copy()
    post_count = len(filtered)
    if post_count < pre_count:
        logger.info(
            "  [IsolationForest] Removed %d multi-dimensional outlier records (contamination=2%%).",
            pre_count - post_count,
        )
    return filtered


def clean_training_data(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """
    IQR法およびIsolation Forestを用いた学習データの自動クレンジング処理
    """
    initial_count = len(df)
    if initial_count == 0:
        return df

    logger.info("Cleaning training data for %s (initial records: %d)...", ptype, initial_count)

    # 1. 物理的な異常値の機械的除外
    df_clean = df[(df["price"] > 50) & (df["area"] > 5.0) & (df["chikunen"] >= 0) & (df["chikunen"] < 100)].copy()
    physical_clean_count = len(df_clean)
    if physical_clean_count < initial_count:
        logger.info("  Removed %d records due to physical limit filters.", initial_count - physical_clean_count)

    if len(df_clean) < 20:
        return df_clean

    # 2. IQR法による価格と面積の外れ値除外
    df_clean = _apply_iqr_filtering(df_clean, ptype)

    # 3. Isolation Forestによる多次元外れ値の検出と除外 (データ数が100件以上の場合のみ)
    if len(df_clean) >= 100:
        df_clean = _apply_isolation_forest_filtering(df_clean, ptype)

    logger.info("Cleaned training data for %s. Final records: %d", ptype, len(df_clean))
    return df_clean
