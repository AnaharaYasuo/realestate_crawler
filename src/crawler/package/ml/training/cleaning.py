"""
学習データ クレンジングモジュール (Issue #715, Issue #1360)
"""

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


def _resolve_reference_land_man(df: pd.DataFrame) -> pd.Series | None:
    if "micro_land_price" in df.columns:
        return pd.to_numeric(df["micro_land_price"], errors="coerce") / 10000.0
    if "average_land_price" in df.columns:
        return pd.to_numeric(df["average_land_price"], errors="coerce") / 10000.0
    return None


def _apply_anchor_ratio_filtering(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """基準地価（ミクロ地価または市区町村地価）に対する実売単価比で桁ミス異常値を除外し、都心適正高額物件を保護する。"""
    ref_man = _resolve_reference_land_man(df)
    if ref_man is None:
        return df

    valid_ref = ref_man.notna() & (ref_man > 0.1)
    if not valid_ref.any():
        return df

    unit_man = pd.to_numeric(df["price"], errors="coerce") / pd.to_numeric(df["area"], errors="coerce").clip(lower=1.0)
    ratio = unit_man / ref_man.clip(lower=0.1)

    if ptype == "tochi":
        keep = (~valid_ref) | ((ratio >= 0.03) & (ratio <= 15.0))
    else:
        max_allowed = ref_man * 18.0 + 120.0
        keep = (~valid_ref) | ((unit_man >= 0.25) & (unit_man <= max_allowed))

    pre_count = len(df)
    filtered = df[keep].copy()
    if len(filtered) < pre_count:
        logger.info("  [AnchorRatio] Removed %d unit-price anomaly records for %s.", pre_count - len(filtered), ptype)
    return filtered


def _anchor_consistent_mask(df: pd.DataFrame, ptype: str) -> pd.Series:
    """高額総額であっても地域の基準地価と㎡単価が整合している都心適正物件を識別しIQR誤除外から保護する。"""
    ref_man = _resolve_reference_land_man(df)
    if ref_man is None:
        return pd.Series(False, index=df.index)
    unit_man = pd.to_numeric(df["price"], errors="coerce") / pd.to_numeric(df["area"], errors="coerce").clip(lower=1.0)
    valid = ref_man.notna() & (ref_man >= 50.0)
    upper_mult = 3.5 if ptype == "tochi" else 8.0
    return valid & (unit_man >= ref_man * 0.25) & (unit_man <= ref_man * upper_mult)


def _apply_iqr_filtering(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """IQR 法による外れ値除去（基準地価整合の都心高額物件保護付き）"""
    filtered_df = df
    for col in ["price", "area"]:
        q1 = filtered_df[col].quantile(0.25)
        q3 = filtered_df[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = max(0.0, q1 - 3.5 * iqr)
        upper_bound = q3 + 3.5 * iqr
        if col == "price":
            upper_bound = max(upper_bound, 60000.0)
        elif col == "area":
            upper_bound = max(upper_bound, 250.0 if ptype == "mansion" else 500.0)

        in_bounds = (filtered_df[col] >= lower_bound) & (filtered_df[col] <= upper_bound)
        if col == "price":
            in_bounds = in_bounds | _anchor_consistent_mask(filtered_df, ptype)

        pre_count = len(filtered_df)
        filtered_df = filtered_df[in_bounds].copy()
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
    features_for_outlier = [c for c in ("price", "area", "chikunen") if c in df.columns]
    if "tochi_menseki" in df.columns and ptype != "mansion":
        features_for_outlier.append("tochi_menseki")

    iso = IsolationForest(contamination=0.02, random_state=42)
    x_outlier = df[features_for_outlier].fillna(0)

    preds = iso.fit_predict(x_outlier)
    keep = (preds == 1) | np.asarray(_anchor_consistent_mask(df, ptype), dtype=bool)
    pre_count = len(df)
    filtered = df[keep].copy()
    post_count = len(filtered)
    if post_count < pre_count:
        logger.info(
            "  [IsolationForest] Removed %d multi-dimensional outlier records (contamination=2%%).",
            pre_count - post_count,
        )
    return filtered


def clean_training_data(df: pd.DataFrame, ptype: str) -> pd.DataFrame:
    """
    共有持分除外・基準地価比（Anchor-Ratio）・IQR法・Isolation Forestを用いた学習データの自動クレンジング処理
    """
    initial_count = len(df)
    if initial_count == 0:
        return df

    logger.info("Cleaning training data for %s (initial records: %d)...", ptype, initial_count)

    # 0. 共有持分のみ売買・底地のみ等の特殊取引除外 (Issue #1360)
    df_work = df
    if "is_special_sale_share" in df_work.columns:
        share_vals = pd.to_numeric(df_work["is_special_sale_share"], errors="coerce").fillna(0.0)
        df_work = df_work[share_vals < 0.5].copy()

    # 1. 物理的な異常値の機械的除外
    cond = (df_work["price"] > 50) & (df_work["area"] > 5.0)
    if "chikunen" in df_work.columns and ptype != "tochi":
        cond = cond & (df_work["chikunen"] >= 0) & (df_work["chikunen"] < 100)
    df_clean = df_work[cond].copy()
    physical_clean_count = len(df_clean)
    if physical_clean_count < initial_count:
        logger.info("  Removed %d records due to physical/special-share filters.", initial_count - physical_clean_count)

    # 1.1 重複物件の除外 (Issue #1284)
    dedup_cols = [c for c in ["price", "area", "prefecture", "city", "chikunen"] if c in df_clean.columns]
    if len(dedup_cols) >= 3:
        pre_dedup = len(df_clean)
        df_clean = df_clean.drop_duplicates(subset=dedup_cols, keep="first").copy()
        post_dedup = len(df_clean)
        if post_dedup < pre_dedup:
            logger.info("  Removed %d duplicate records based on %s.", pre_dedup - post_dedup, dedup_cols)

    # 1.2 基準地価比による桁ミス・入力異常除外
    df_clean = _apply_anchor_ratio_filtering(df_clean, ptype)

    if len(df_clean) < 20:
        return df_clean

    # 2. IQR法による価格と面積の外れ値除外
    df_clean = _apply_iqr_filtering(df_clean, ptype)

    # 3. Isolation Forestによる多次元外れ値の検出と除外 (データ数が100件以上の場合のみ)
    if len(df_clean) >= 100:
        df_clean = _apply_isolation_forest_filtering(df_clean, ptype)

    logger.info("Cleaned training data for %s. Final records: %d", ptype, len(df_clean))
    return df_clean
