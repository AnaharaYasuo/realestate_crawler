"""国土地理院（GSI）無料標高タイル（5mレーザ DEM5A / 10m DEM）による微地形・傾斜・ひな段解析 (Issue #1360)

APIキー不要の国土地理院公式標高PNGタイル仕様（24bit RGB, 0.01m単位, 無効値 x=2^23）に基づき、
現地標高・Horn法3x3敷地傾斜角・南北傾斜方位（南ひな段 vs 北下がり）・局所窪地深さを算出する。
"""

from __future__ import annotations

import io
import json
import logging
import math
import threading
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)

GSI_DEM5A_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/{z}/{x}/{y}.png"
GSI_DEM10B_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png"
_NODATA_RAW = 8388608  # 2^23 (RGB = 128, 0, 0)
_TWO_POW_24 = 16777216
_DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "gsi_dem_terrain_cache.json"

_CACHE_LOCK = threading.Lock()
_TERRAIN_CACHE: dict[str, tuple[float, float, float, float]] = {}
_TILE_ARRAY_CACHE: dict[tuple[str, int, int, int], np.ndarray | None] = {}
_DISK_LOADED = False


@dataclass(slots=True, frozen=True)
class DemTerrainFeatures:
    """座標周辺の微地形解析結果"""

    dem_elevation_m: float = 0.0
    dem_slope_deg: float = 0.0
    dem_south_aspect_score: float = 0.0
    dem_depression_depth_m: float = 0.0


DEFAULT_DEM_FEATURES = DemTerrainFeatures()


def coord_cache_key(lat: float, lon: float) -> str:
    """約11mメッシュ相当（小数第4位）の正規化座標キーを返す。"""
    return f"{round(float(lat), 4):.4f},{round(float(lon), 4):.4f}"


def _parse_terrain_json(raw: object) -> None:
    if not isinstance(raw, dict):
        return
    for k, v in raw.items():
        if isinstance(v, list) and len(v) == 4:
            _TERRAIN_CACHE[str(k)] = (float(v[0]), float(v[1]), float(v[2]), float(v[3]))


def _ensure_disk_cache_loaded(cache_path: Path) -> None:
    global _DISK_LOADED
    if _DISK_LOADED:
        return
    with _CACHE_LOCK:
        if _DISK_LOADED:
            return
        if cache_path.exists():
            try:
                _parse_terrain_json(json.loads(cache_path.read_text(encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load GSI DEM terrain cache from %s: %s", cache_path, e)
        _DISK_LOADED = True


def _persist_terrain_cache(target_path: Path) -> None:
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: [round(x, 3) for x in v] for k, v in _TERRAIN_CACHE.items()}
        target_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to persist GSI DEM terrain cache: %s", e)


def lookup_cached_dem_features(
    lat: float | None,
    lon: float | None,
    cache_path: Path | None = None,
) -> DemTerrainFeatures:
    """外部通信を一切行わずローカルキャッシュのみから微地形特徴量を返す（ML特徴量抽出用）。"""
    if lat is None or lon is None:
        return DEFAULT_DEM_FEATURES
    target_path = cache_path or _DEFAULT_CACHE_PATH
    _ensure_disk_cache_loaded(target_path)
    hit = _TERRAIN_CACHE.get(coord_cache_key(lat, lon))
    if hit is None:
        return DEFAULT_DEM_FEATURES
    return DemTerrainFeatures(*hit)


def latlon_to_tile_pixel(lat: float, lon: float, zoom: int) -> tuple[int, int, int, int]:
    """緯度経度を Web Mercator タイル座標 `(xtile, ytile)` とタイル内ピクセル `(px, py)` に変換する。"""
    n = float(1 << zoom)
    xtile_f = (float(lon) + 180.0) / 360.0 * n
    lat_rad = math.radians(max(-85.05, min(85.05, float(lat))))
    ytile_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    xtile = int(xtile_f)
    ytile = int(ytile_f)
    px = min(255, max(0, int((xtile_f - xtile) * 256.0)))
    py = min(255, max(0, int((ytile_f - ytile) * 256.0)))
    return xtile, ytile, px, py


def decode_gsi_dem_png_bytes(png_bytes: bytes) -> np.ndarray:
    """国土地理院 標高PNGバイト列を `float64 (256, 256)` 標高配列（m, 無効値は `np.nan`）に復号する。"""
    rgb = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB"), dtype=np.int64)
    raw = (rgb[:, :, 0] << 16) + (rgb[:, :, 1] << 8) + rgb[:, :, 2]
    signed = np.where(raw < _NODATA_RAW, raw, raw - _TWO_POW_24)
    elev = signed.astype(np.float64) * 0.01
    elev[raw == _NODATA_RAW] = np.nan
    return elev


def _fetch_tile_array(layer: str, zoom: int, xtile: int, ytile: int, timeout: float = 8.0) -> np.ndarray | None:
    cache_key = (layer, zoom, xtile, ytile)
    with _CACHE_LOCK:
        if cache_key in _TILE_ARRAY_CACHE:
            return _TILE_ARRAY_CACHE[cache_key]

    url_tmpl = GSI_DEM5A_URL if layer == "dem5a" else GSI_DEM10B_URL
    url = url_tmpl.format(z=zoom, x=xtile, y=ytile)
    arr: np.ndarray | None = None
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            arr = decode_gsi_dem_png_bytes(resp.content)
    except Exception as e:  # noqa: BLE001
        logger.debug("GSI DEM tile fetch failed (%s): %s", url, e)

    with _CACHE_LOCK:
        if len(_TILE_ARRAY_CACHE) > 2048:
            _TILE_ARRAY_CACHE.clear()
        _TILE_ARRAY_CACHE[cache_key] = arr
    return arr


def compute_terrain_from_grid(
    grid: np.ndarray,
    px: int,
    py: int,
    lat: float,
    zoom: int,
    step_px: int = 2,
) -> DemTerrainFeatures | None:
    """256x256 標高グリッド内の `(px, py)` と8近傍から傾斜角・南ひな段スコア・窪地深さを計算する。"""
    if grid is None or grid.shape[0] < 3 or grid.shape[1] < 3:
        return None
    z_c = float(grid[py, px])
    if math.isnan(z_c):
        return None

    x0, x1 = max(0, px - step_px), min(255, px + step_px)
    y0, y1 = max(0, py - step_px), min(255, py + step_px)
    meters_per_px = (156543.03392 * math.cos(math.radians(lat))) / float(1 << (zoom + 8))
    dx_m = max(1.0, (x1 - x0) * meters_per_px)
    dy_m = max(1.0, (y1 - y0) * meters_per_px)

    def _val(yy: int, xx: int) -> float:
        v = float(grid[yy, xx])
        return z_c if math.isnan(v) else v

    z_nw, z_n, z_ne = _val(y0, x0), _val(y0, px), _val(y0, x1)
    z_w, z_e = _val(py, x0), _val(py, x1)
    z_sw, z_s, z_se = _val(y1, x0), _val(y1, px), _val(y1, x1)

    dz_dx = ((z_ne + 2.0 * z_e + z_se) - (z_nw + 2.0 * z_w + z_sw)) / (4.0 * dx_m)
    dz_dy = ((z_n + 0.5 * (z_nw + z_ne)) - (z_s + 0.5 * (z_sw + z_se))) / (2.0 * dy_m)
    slope_deg = math.degrees(math.atan(math.hypot(dz_dx, dz_dy)))

    north_minus_south = ((z_nw + z_n + z_ne) - (z_sw + z_s + z_se)) / 3.0
    south_aspect = math.tanh((north_minus_south / dy_m) * 8.0)

    mean_neighbors = (z_nw + z_n + z_ne + z_w + z_e + z_sw + z_s + z_se) / 8.0
    depression_m = mean_neighbors - z_c

    return DemTerrainFeatures(
        dem_elevation_m=round(z_c, 2),
        dem_slope_deg=round(max(0.0, slope_deg), 2),
        dem_south_aspect_score=round(south_aspect, 3),
        dem_depression_depth_m=round(depression_m, 2),
    )


def fetch_and_compute_dem_features(
    lat: float,
    lon: float,
    *,
    persist_cache: bool = False,
    cache_path: Path | None = None,
) -> DemTerrainFeatures:
    """5mレーザDEM（zoom 15）優先、欠損時は10m DEM（zoom 14）へフォールバックして微地形特徴量を算出する。"""
    target_path = cache_path or _DEFAULT_CACHE_PATH
    _ensure_disk_cache_loaded(target_path)
    key = coord_cache_key(lat, lon)
    with _CACHE_LOCK:
        if key in _TERRAIN_CACHE:
            return DemTerrainFeatures(*_TERRAIN_CACHE[key])

    res: DemTerrainFeatures | None = None
    for layer, zoom, step_px in (("dem5a", 15, 2), ("dem10b", 14, 1)):
        xt, yt, px, py = latlon_to_tile_pixel(lat, lon, zoom)
        arr = _fetch_tile_array(layer, zoom, xt, yt)
        if arr is not None:
            res = compute_terrain_from_grid(arr, px, py, lat, zoom, step_px=step_px)
            if res is not None:
                break

    final = res or DEFAULT_DEM_FEATURES
    with _CACHE_LOCK:
        _TERRAIN_CACHE[key] = (
            final.dem_elevation_m,
            final.dem_slope_deg,
            final.dem_south_aspect_score,
            final.dem_depression_depth_m,
        )
        if persist_cache:
            _persist_terrain_cache(target_path)
    return final


def _process_tile_group(
    zoom15_tile: tuple[int, int],
    pts: list[tuple[str, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    xt15, yt15 = zoom15_tile
    arr15 = _fetch_tile_array("dem5a", 15, xt15, yt15)
    out: dict[str, tuple[float, float, float, float]] = {}
    for key, lat, lon in pts:
        _, _, px15, py15 = latlon_to_tile_pixel(lat, lon, 15)
        feat = compute_terrain_from_grid(arr15, px15, py15, lat, 15, step_px=2) if arr15 is not None else None
        if feat is None:
            xt14, yt14, px14, py14 = latlon_to_tile_pixel(lat, lon, 14)
            arr14 = _fetch_tile_array("dem10b", 14, xt14, yt14)
            feat = compute_terrain_from_grid(arr14, px14, py14, lat, 14, step_px=1) if arr14 is not None else None
        resolved = feat or DEFAULT_DEM_FEATURES
        out[key] = (
            resolved.dem_elevation_m,
            resolved.dem_slope_deg,
            resolved.dem_south_aspect_score,
            resolved.dem_depression_depth_m,
        )
    return out


def batch_warm_dem_cache(
    coords: Iterable[tuple[float, float]],
    *,
    max_workers: int = 8,
    cache_path: Path | None = None,
) -> int:
    """座標リストをタイル単位に集約して並列取得し、微地形特徴量キャッシュを一括更新・保存する。"""
    target_path = cache_path or _DEFAULT_CACHE_PATH
    _ensure_disk_cache_loaded(target_path)

    tile_groups: dict[tuple[int, int], list[tuple[str, float, float]]] = defaultdict(list)
    seen_keys: set[str] = set()
    for lat, lon in coords:
        key = coord_cache_key(lat, lon)
        if key in seen_keys or key in _TERRAIN_CACHE:
            continue
        seen_keys.add(key)
        xt15, yt15, _, _ = latlon_to_tile_pixel(lat, lon, 15)
        tile_groups[(xt15, yt15)].append((key, float(lat), float(lon)))

    if not tile_groups:
        return 0

    computed = 0
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futs = [pool.submit(_process_tile_group, t_key, pts) for t_key, pts in tile_groups.items()]
        for fut in as_completed(futs):
            group_res = fut.result()
            with _CACHE_LOCK:
                _TERRAIN_CACHE.update(group_res)
            computed += len(group_res)

    with _CACHE_LOCK:
        _persist_terrain_cache(target_path)
    return computed


def seed_dem_cache_entry(
    lat: float,
    lon: float,
    feat: DemTerrainFeatures,
    cache_path: Path | None = None,
) -> None:
    """テスト用: 指定座標の微地形特徴量をメモリキャッシュへ直接登録する。"""
    target_path = cache_path or _DEFAULT_CACHE_PATH
    _ensure_disk_cache_loaded(target_path)
    with _CACHE_LOCK:
        _TERRAIN_CACHE[coord_cache_key(lat, lon)] = (
            feat.dem_elevation_m,
            feat.dem_slope_deg,
            feat.dem_south_aspect_score,
            feat.dem_depression_depth_m,
        )


def reset_dem_cache() -> None:
    """テスト用: 微地形キャッシュおよびタイルキャッシュをリセットする。"""
    global _DISK_LOADED
    with _CACHE_LOCK:
        _TERRAIN_CACHE.clear()
        _TILE_ARRAY_CACHE.clear()
        _DISK_LOADED = False
