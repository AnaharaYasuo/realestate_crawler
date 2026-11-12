"""
階層ベイズ縮小（Hierarchical Empirical-Bayes Shrinkage）および
`scipy.spatial.cKDTree` 空間 k-NN によるリークなし Out-of-Fold 空間ターゲットエンコーダ (Issue #1360, #1380)

階層構造:
1. 同一マンション棟 (`building_group`) ➔ 町丁目 (`chome_group`) ➔ 市区町村 (`(prefecture, city)`) ➔ 都道府県 (`prefecture`) ➔ 全国平均 (`global_mean`)
2. 駅×徒歩圏帯 (`(prefecture, station, walk_band)`) ➔ 駅 (`(prefecture, station)`) ➔ 市区町村 ➔ 都道府県 ➔ 全国平均
3. 半径500m空間 k-NN (`cKDTree`, 同一 `building_group` 除外・距離逆べき乗重み) ➔ 町丁目事前分布へベイズ縮小
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.model_selection import GroupKFold

_LAT_TO_M = 111120.0
_LON_TO_M = 90160.0
_KNN_RADIUS_M = 500.0
_KNN_MAX_K = 24
_KNN_PRIOR_WEIGHT = 1.5


def _walk_band_array(walk_series: pd.Series) -> np.ndarray:
    vals = pd.to_numeric(walk_series, errors="coerce").fillna(15.0).to_numpy(dtype=float)
    bands = np.full(len(vals), 3, dtype=int)
    bands = np.where(vals <= 15.0, 2, bands)
    bands = np.where(vals <= 10.0, 1, bands)
    bands = np.where(vals <= 5.0, 0, bands)
    return bands


def _clean_str_col(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    if col not in df.columns:
        return np.full(n, "", dtype=object)
    return df[col].fillna("").astype(str).str.strip().to_numpy()


def _extract_location_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    pref = _clean_str_col(df, "prefecture", n)
    city = _clean_str_col(df, "city", n)
    chome = _clean_str_col(df, "chome_group", n)
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


def _extract_building_and_coords(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`building_group` と平面メートル座標 `(N, 2)` および有効マスク `(N,)` を抽出する。"""
    n = len(df)
    bldg = _clean_str_col(df, "building_group", n)
    lat = (
        pd.to_numeric(df["latitude"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        if "latitude" in df.columns
        else np.zeros(n, dtype=float)
    )
    lon = (
        pd.to_numeric(df["longitude"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        if "longitude" in df.columns
        else np.zeros(n, dtype=float)
    )
    valid = (lat > 20.0) & (lat < 46.5) & (lon > 122.0) & (lon < 154.5)
    coords_m = np.column_stack((lat * _LAT_TO_M, lon * _LON_TO_M)).astype(np.float32)
    return bldg, coords_m, valid


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
    building_map: dict[str, float] = field(default_factory=dict)
    coords_m: np.ndarray | None = None
    coords_y: np.ndarray | None = None
    coords_w: np.ndarray | None = None
    coords_bldg: np.ndarray | None = None


def _fit_building_map(
    bldg: np.ndarray,
    chome: np.ndarray,
    pref: np.ndarray,
    city: np.ndarray,
    y_arr: np.ndarray,
    w_arr: np.ndarray,
    chome_map: dict[str, float],
    city_map: dict[tuple[str, str], float],
    pref_map: dict[str, float],
    global_mean: float,
    smoothing: float,
) -> dict[str, float]:
    m_bldg = max(1.5, smoothing * 0.5)
    bldg_parent: dict[str, tuple[str, str, str]] = {}
    for b, ch, p, c in zip(bldg, chome, pref, city):
        if b and b not in bldg_parent:
            bldg_parent[str(b)] = (str(ch), str(p), str(c))
    bldg_stats = _weighted_group_stats(list(bldg), y_arr, w_arr)
    out: dict[str, float] = {}
    for b_key, (cnt, mean) in bldg_stats.items():
        ch_k, p_k, c_k = bldg_parent.get(b_key, ("", "", ""))
        city_prior = city_map.get((p_k, c_k), pref_map.get(p_k, global_mean))
        prior = chome_map.get(ch_k, city_prior) if ch_k else city_prior
        out[b_key] = (cnt * mean + m_bldg * prior) / (cnt + m_bldg)
    return out


def _fit_station_maps(
    pref: np.ndarray,
    city: np.ndarray,
    station: np.ndarray,
    walk_band: np.ndarray,
    y_arr: np.ndarray,
    w_arr: np.ndarray,
    city_map: dict[tuple[str, str], float],
    pref_map: dict[str, float],
    global_mean: float,
    m_city: float,
    m_leaf: float,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str, int], float]]:
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
    station_band_map: dict[tuple[str, str, int], float] = {
        (p, st, wb): (cnt * mean + m_leaf * station_map.get((p, st), pref_map.get(p, global_mean))) / (cnt + m_leaf)
        for (p, st, wb), (cnt, mean) in sb_stats.items()
    }
    return station_map, station_band_map


def _extract_valid_coord_arrays(
    coords_m: np.ndarray | None,
    valid_coords: np.ndarray | None,
    y_arr: np.ndarray,
    w_arr: np.ndarray,
    bldg: np.ndarray | None,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    if coords_m is None or valid_coords is None or not np.any(valid_coords):
        return None, None, None, None
    c_m = coords_m[valid_coords].astype(np.float32)
    c_y = y_arr[valid_coords].astype(np.float32)
    c_w = w_arr[valid_coords].astype(np.float32)
    c_b = bldg[valid_coords] if bldg is not None else np.full(len(c_y), "", dtype=object)
    return c_m, c_y, c_w, c_b


def _fit_state_from_arrays(
    pref: np.ndarray,
    city: np.ndarray,
    chome: np.ndarray,
    station: np.ndarray,
    walk_band: np.ndarray,
    y_arr: np.ndarray,
    w_arr: np.ndarray,
    smoothing: float,
    bldg: np.ndarray | None = None,
    coords_m: np.ndarray | None = None,
    valid_coords: np.ndarray | None = None,
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
    chome_map = {
        ch: (
            cnt * mean
            + m_leaf
            * city_map.get(chome_parent.get(ch, ("", "")), pref_map.get(chome_parent.get(ch, ("", ""))[0], global_mean))
        )
        / (cnt + m_leaf)
        for ch, (cnt, mean) in chome_stats.items()
    }

    station_map, station_band_map = _fit_station_maps(
        pref, city, station, walk_band, y_arr, w_arr, city_map, pref_map, global_mean, m_city, m_leaf
    )
    building_map = (
        _fit_building_map(
            bldg, chome, pref, city, y_arr, w_arr, chome_map, city_map, pref_map, global_mean, smoothing
        )
        if bldg is not None
        else {}
    )
    c_m, c_y, c_w, c_b = _extract_valid_coord_arrays(coords_m, valid_coords, y_arr, w_arr, bldg)

    return _HierarchyState(
        global_mean=global_mean,
        pref_map=pref_map,
        city_map=city_map,
        chome_map=chome_map,
        station_map=station_map,
        station_band_map=station_band_map,
        building_map=building_map,
        coords_m=c_m,
        coords_y=c_y,
        coords_w=c_w,
        coords_bldg=c_b,
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


def _score_single_knn_query(
    dists: np.ndarray,
    idxs: np.ndarray,
    ref_n: int,
    query_bldg: str,
    ref_y: np.ndarray,
    ref_w: np.ndarray,
    ref_bldg: np.ndarray,
    chome_prior: float,
) -> tuple[float, float]:
    sum_w = 0.0
    sum_wy = 0.0
    count = 0.0
    for d_m, j in zip(dists, idxs):
        if j >= ref_n or not np.isfinite(d_m):
            break
        if query_bldg and str(ref_bldg[j]) == query_bldg:
            continue
        wj = float(ref_w[j]) / (1.0 + float(d_m) / 200.0)
        sum_w += wj
        sum_wy += wj * float(ref_y[j])
        count += 1.0
    if count <= 0.0 or sum_w <= 0.0:
        return chome_prior, 0.0
    shrunk = (sum_wy + _KNN_PRIOR_WEIGHT * chome_prior) / (sum_w + _KNN_PRIOR_WEIGHT)
    return float(shrunk), count


def _predict_knn_and_building(
    state: _HierarchyState,
    bldg: np.ndarray,
    coords_m: np.ndarray,
    valid_coords: np.ndarray,
    out_chome: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(bldg)
    bldg_map = getattr(state, "building_map", None) or {}
    out_bldg = np.array(
        [float(bldg_map.get(str(bldg[i]), out_chome[i])) if bldg[i] else float(out_chome[i]) for i in range(n)],
        dtype=np.float32,
    )
    out_knn = out_chome.astype(np.float32).copy()
    out_cnt = np.zeros(n, dtype=np.float32)

    ref_m = getattr(state, "coords_m", None)
    ref_y = getattr(state, "coords_y", None)
    ref_w = getattr(state, "coords_w", None)
    ref_b = getattr(state, "coords_bldg", None)
    if ref_m is None or ref_y is None or ref_w is None or ref_b is None or len(ref_m) == 0:
        return out_bldg, out_knn, out_cnt
    if not np.any(valid_coords):
        return out_bldg, out_knn, out_cnt

    tree = cKDTree(ref_m)
    k_use = min(_KNN_MAX_K, len(ref_m))
    valid_indices = np.flatnonzero(valid_coords)
    dists_mat, idxs_mat = tree.query(coords_m[valid_indices], k=k_use, distance_upper_bound=_KNN_RADIUS_M)
    if k_use == 1:
        dists_mat = dists_mat[:, None]
        idxs_mat = idxs_mat[:, None]

    ref_n = len(ref_m)
    for pos, row_i in enumerate(valid_indices):
        knn_val, cnt_val = _score_single_knn_query(
            dists_mat[pos],
            idxs_mat[pos],
            ref_n,
            str(bldg[row_i]),
            ref_y,
            ref_w,
            ref_b,
            float(out_chome[row_i]),
        )
        out_knn[row_i] = knn_val
        out_cnt[row_i] = cnt_val

    return out_bldg, out_knn, out_cnt


class MicroLocationTargetEncoder:
    """学習時は Out-of-Fold でリークゼロ変換し、推論時は全学習統計と空間 k-NN で補完するエンコーダ。"""

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
        bldg, coords_m, valid_coords = _extract_building_and_coords(df)
        y_arr = np.asarray(y, dtype=float)
        w_arr = (
            np.maximum(1e-6, np.asarray(sample_weight, dtype=float))
            if sample_weight is not None and len(sample_weight) == len(y_arr)
            else np.ones(len(y_arr), dtype=float)
        )
        self._state = _fit_state_from_arrays(
            pref, city, chome, station, walk_band, y_arr, w_arr, self.smoothing,
            bldg=bldg, coords_m=coords_m, valid_coords=valid_coords,
        )
        return self

    def fit_transform_oof_extended(
        self,
        df: pd.DataFrame,
        y: pd.Series | np.ndarray,
        cv: Any,
        groups: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> dict[str, np.ndarray]:
        """町丁目・駅徒歩圏・同一棟・半径500m空間k-NNの5特徴量をリークゼロ OOF で一括算出する。"""
        n = len(df)
        if n == 0:
            z = np.zeros(0, dtype=np.float32)
            return {
                "chome_oof": z,
                "station_walk_oof": z.copy(),
                "building_oof": z.copy(),
                "knn_500m_oof": z.copy(),
                "knn_500m_count": z.copy(),
            }

        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        bldg, coords_m, valid_coords = _extract_building_and_coords(df)
        y_arr = np.asarray(y, dtype=float)
        w_arr = (
            np.maximum(1e-6, np.asarray(sample_weight, dtype=float))
            if sample_weight is not None and len(sample_weight) == len(y_arr)
            else np.ones(n, dtype=float)
        )

        oof_chome = np.zeros(n, dtype=float)
        oof_st = np.zeros(n, dtype=float)
        oof_bldg = np.zeros(n, dtype=float)
        oof_knn = np.zeros(n, dtype=float)
        oof_knn_cnt = np.zeros(n, dtype=float)
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
                bldg=bldg[train_idx],
                coords_m=coords_m[train_idx],
                valid_coords=valid_coords[train_idx],
            )
            val_ch, val_st = _predict_from_state(
                fold_state,
                pref[val_idx], city[val_idx], chome[val_idx],
                station[val_idx], walk_band[val_idx],
            )
            val_bldg, val_knn, val_cnt = _predict_knn_and_building(
                fold_state,
                bldg[val_idx],
                coords_m[val_idx],
                valid_coords[val_idx],
                val_ch,
            )
            oof_chome[val_idx] += val_ch
            oof_st[val_idx] += val_st
            oof_bldg[val_idx] += val_bldg
            oof_knn[val_idx] += val_knn
            oof_knn_cnt[val_idx] += val_cnt
            oof_counts[val_idx] += 1.0

        denom = np.maximum(1.0, oof_counts)
        self._state = _fit_state_from_arrays(
            pref, city, chome, station, walk_band, y_arr, w_arr, self.smoothing,
            bldg=bldg, coords_m=coords_m, valid_coords=valid_coords,
        )
        return {
            "chome_oof": (oof_chome / denom).astype(np.float32),
            "station_walk_oof": (oof_st / denom).astype(np.float32),
            "building_oof": (oof_bldg / denom).astype(np.float32),
            "knn_500m_oof": (oof_knn / denom).astype(np.float32),
            "knn_500m_count": (oof_knn_cnt / denom).astype(np.float32),
        }

    def fit_transform_oof(
        self,
        df: pd.DataFrame,
        y: pd.Series | np.ndarray,
        cv: Any,
        groups: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        ext = self.fit_transform_oof_extended(df, y, cv, groups=groups, sample_weight=sample_weight)
        return ext["chome_oof"], ext["station_walk_oof"]

    def transform_extended(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        if len(df) == 0:
            z = np.zeros(0, dtype=np.float32)
            return {
                "chome_oof": z,
                "station_walk_oof": z.copy(),
                "building_oof": z.copy(),
                "knn_500m_oof": z.copy(),
                "knn_500m_count": z.copy(),
            }
        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        bldg, coords_m, valid_coords = _extract_building_and_coords(df)
        ch_arr, st_arr = _predict_from_state(self._state, pref, city, chome, station, walk_band)
        bldg_arr, knn_arr, cnt_arr = _predict_knn_and_building(
            self._state, bldg, coords_m, valid_coords, ch_arr
        )
        return {
            "chome_oof": ch_arr,
            "station_walk_oof": st_arr,
            "building_oof": bldg_arr,
            "knn_500m_oof": knn_arr,
            "knn_500m_count": cnt_arr,
        }

    def transform(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if len(df) == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
        pref, city, chome, station, walk_band = _extract_location_arrays(df)
        return _predict_from_state(self._state, pref, city, chome, station, walk_band)
