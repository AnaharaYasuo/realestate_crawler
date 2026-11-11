"""
階層ベイズ縮小（Hierarchical Empirical-Bayes Shrinkage）によるリークなし
Out-of-Fold 空間ターゲットエンコーダ (Issue #1360)

階層構造:
1. 町丁目 (`chome_group`) ➔ 市区町村 (`(prefecture, city)`) ➔ 都道府県 (`prefecture`) ➔ 全国平均 (`global_mean`)
2. 駅×徒歩圏帯 (`(prefecture, station, walk_band)`) ➔ 駅 (`(prefecture, station)`) ➔ 市区町村 ➔ 都道府県 ➔ 全国平均
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def _walk_band_array(walk_series: pd.Series) -> np.ndarray:
    vals = pd.to_numeric(walk_series, errors="coerce").fillna(15.0).to_numpy(dtype=float)
    bands = np.full(len(vals), 3, dtype=int)
    bands = np.where(vals <= 15.0, 2, bands)
    bands = np.where(vals <= 10.0, 1, bands)
    bands = np.where(vals <= 5.0, 0, bands)
    return bands


def _extract_location_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    pref = (
        df["prefecture"].fillna("").astype(str).str.strip().to_numpy()
        if "prefecture" in df.columns
        else np.full(n, "", dtype=object)
    )
    city = (
        df["city"].fillna("").astype(str).str.strip().to_numpy()
        if "city" in df.columns
        else np.full(n, "", dtype=object)
    )
    chome = (
        df["chome_group"].fillna("").astype(str).str.strip().to_numpy()
        if "chome_group" in df.columns
        else np.full(n, "", dtype=object)
    )
    station_raw = (
        df["station"].fillna("").astype(str).str.replace("駅", "", regex=False).str.strip().to_numpy()
        if "station" in df.columns
        else np.full(n, "", dtype=object)
    )
    walk_bands = (
        _walk_band_array(df["effective_walk_min"])
        if "effective_walk_min" in df.columns
        else np.full(n, 2, dtype=int)
    )
    return pref, city, chome, station_raw, walk_bands


def _weighted_group_stats(keys: list[Any], y_arr: np.ndarray, w_arr: np.ndarray) -> dict[Any, tuple[float, float]]:
    """キーごとの `(重み合計 W, 重み付き平均 mean)` を集計（空キーは除外）"""
    sum_w: dict[Any, float] = {}
    sum_wy: dict[Any, float] = {}
    for k, yv, wv in zip(keys, y_arr, w_arr):
        if not k or (isinstance(k, tuple) and not all(str(part) != "" for part in k)):
            continue
        sum_w[k] = sum_w.get(k, 0.0) + float(wv)
        sum_wy[k] = sum_wy.get(k, 0.0) + float(wv) * float(yv)
    return {k: (sw, sum_wy[k] / sw) for k, sw in sum_w.items() if sw > 0.0}


@dataclass
class _HierarchyState:
    global_mean: float = 0.0
    pref_map: dict[str, float] = field(default_factory=dict)
    city_map: dict[tuple[str, str], float] = field(default_factory=dict)
    chome_map: dict[str, float] = field(default_factory=dict)
    station_map: dict[tuple[str, str], float] = field(default_factory=dict)
    station_band_map: dict[tuple[str, str, int], float] = field(default_factory=dict)


def _fit_state_from_arrays(
    pref: np.ndarray,
    city: np.ndarray,
    chome: np.ndarray,
    station: np.ndarray,
    walk_band: np.ndarray,
    y_arr: np.ndarray,
    w_arr: np.ndarray,
    smoothing: float,
) -> _HierarchyState:
    if len(y_arr) == 0:
        return _HierarchyState()

    total_w = float(np.sum(w_arr))
    global_mean = float(np.sum(y_arr * w_arr) / total_w) if total_w > 0 else float(np.mean(y_arr))
    m_pref = max(2.0, smoothing * 0.6)
    m_city = max(2.0, smoothing * 0.8)
    m_leaf = max(1.0, smoothing)

    pref_stats = _weighted_group_stats(list(pref), y_arr, w_arr)
    pref_map = {
        p: (cnt * mean + m_pref * global_mean) / (cnt + m_pref)
        for p, (cnt, mean) in pref_stats.items()
    }

    city_keys = [(str(p), str(c)) for p, c in zip(pref, city)]
    city_stats = _weighted_group_stats(city_keys, y_arr, w_arr)
    city_map = {
        (p, c): (cnt * mean + m_city * pref_map.get(p, global_mean)) / (cnt + m_city)
        for (p, c), (cnt, mean) in city_stats.items()
    }

    chome_parent: dict[str, tuple[str, str]] = {}
    for p, c, ch in zip(pref, city, chome):
        if ch and ch not in chome_parent:
            chome_parent[str(ch)] = (str(p), str(c))
    chome_stats = _weighted_group_stats(list(chome), y_arr, w_arr)
    chome_map: dict[str, float] = {}
    for ch, (cnt, mean) in chome_stats.items():
        p_key, c_key = chome_parent.get(ch, ("", ""))
        prior = city_map.get((p_key, c_key), pref_map.get(p_key, global_mean))
        chome_map[ch] = (cnt * mean + m_leaf * prior) / (cnt + m_leaf)

    st_parent_city: dict[tuple[str, str], tuple[str, str]] = {}
    for p, c, st in zip(pref, city, station):
        if p and st and (p, st) not in st_parent_city:
            st_parent_city[(str(p), str(st))] = (str(p), str(c))
    st_keys = [(str(p), str(st)) for p, st in zip(pref, station)]
    st_stats = _weighted_group_stats(st_keys, y_arr, w_arr)
    station_map: dict[tuple[str, str], float] = {}
    for (p, st), (cnt, mean) in st_stats.items():
        parent_c = st_parent_city.get((p, st), (p, ""))
        prior = city_map.get(parent_c, pref_map.get(p, global_mean))
        station_map[(p, st)] = (cnt * mean + m_city * prior) / (cnt + m_city)

    sb_keys = [(str(p), str(st), int(wb)) for p, st, wb in zip(pref, station, walk_band)]
    sb_stats = _weighted_group_stats(sb_keys, y_arr, w_arr)
    station_band_map: dict[tuple[str, str, int], float] = {}
    for (p, st, wb), (cnt, mean) in sb_stats.items():
        prior = station_map.get((p, st), pref_map.get(p, global_mean))
        station_band_map[(p, st, wb)] = (cnt * mean + m_leaf * prior) / (cnt + m_leaf)

    return _HierarchyState(
        global_mean=global_mean,
        pref_map=pref_map,
        city_map=city_map,
        chome_map=chome_map,
        station_map=station_map,
        station_band_map=station_band_map,
    )


def _predict_from_state(
    state: _HierarchyState,
    pref: np.ndarray,
    city: np.ndarray,
    chome: np.ndarray,
    station: np.ndarray,
    walk_band: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    n = len(pref)
    out_chome = np.empty(n, dtype=np.float32)
    out_st = np.empty(n, dtype=np.float32)
    g_mean = state.global_mean

    for i in range(n):
        p = str(pref[i])
        c = str(city[i])
        ch = str(chome[i])
        st = str(station[i])
        wb = int(walk_band[i])

        city_prior = state.city_map.get((p, c), state.pref_map.get(p, g_mean))
        out_chome[i] = float(state.chome_map.get(ch, city_prior)) if ch else float(city_prior)

        if p and st:
            st_prior = state.station_map.get((p, st), city_prior)
            out_st[i] = float(state.station_band_map.get((p, st, wb), st_prior))
        else:
            out_st[i] = float(city_prior)

    return out_chome, out_st


class MicroLocationTargetEncoder:
    """学習時は Out-of-Fold でリークゼロ変換し、推論時は全学習統計で未知町丁目も階層補完するエンコーダ。"""

    def __init__(self, smoothing: float = 8.0) -> None:
        self.smoothing = float(smoothing)
        self._state = _HierarchyState()

    def fit(
        self,
        df: pd.DataFrame,
        y: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> MicroLocationTargetEncoder:
        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        y_arr = np.asarray(y, dtype=float)
        w_arr = (
            np.maximum(1e-6, np.asarray(sample_weight, dtype=float))
            if sample_weight is not None and len(sample_weight) == len(y_arr)
            else np.ones(len(y_arr), dtype=float)
        )
        self._state = _fit_state_from_arrays(
            pref, city, chome, station, walk_band, y_arr, w_arr, self.smoothing
        )
        return self

    def fit_transform_oof(
        self,
        df: pd.DataFrame,
        y: pd.Series | np.ndarray,
        cv: Any,
        groups: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        n = len(df)
        if n == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)

        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        y_arr = np.asarray(y, dtype=float)
        w_arr = (
            np.maximum(1e-6, np.asarray(sample_weight, dtype=float))
            if sample_weight is not None and len(sample_weight) == len(y_arr)
            else np.ones(n, dtype=float)
        )

        oof_chome = np.zeros(n, dtype=float)
        oof_st = np.zeros(n, dtype=float)
        oof_counts = np.zeros(n, dtype=float)

        split_iter = (
            cv.split(df, y_arr, groups)
            if isinstance(cv, GroupKFold) and groups is not None
            else cv.split(df)
        )
        for train_idx, val_idx in split_iter:
            fold_state = _fit_state_from_arrays(
                pref[train_idx], city[train_idx], chome[train_idx],
                station[train_idx], walk_band[train_idx],
                y_arr[train_idx], w_arr[train_idx], self.smoothing,
            )
            val_ch, val_st = _predict_from_state(
                fold_state,
                pref[val_idx], city[val_idx], chome[val_idx],
                station[val_idx], walk_band[val_idx],
            )
            oof_chome[val_idx] += val_ch
            oof_st[val_idx] += val_st
            oof_counts[val_idx] += 1.0

        denom = np.maximum(1.0, oof_counts)
        oof_chome /= denom
        oof_st /= denom

        # 推論用に全学習データでの最終階層統計を保持
        self._state = _fit_state_from_arrays(
            pref, city, chome, station, walk_band, y_arr, w_arr, self.smoothing
        )
        return oof_chome.astype(np.float32), oof_st.astype(np.float32)

    def transform(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if len(df) == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        return _predict_from_state(self._state, pref, city, chome, station, walk_band)
