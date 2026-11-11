"""国土地理院（GSI）無料アドレス検索APIによるバッチジオコーダ＆ローカルキャッシュ (Issue #1360)

APIキー不要・完全無料の国土地理院 AddressSearch エンドポイントを利用し、
推論時の外部通信を避けるためバッチ事前解決およびローカル JSON キャッシュに対応する。
"""

import json
import logging
import threading
import unicodedata
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
_DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "gsi_geocode_cache.json"
_CACHE_LOCK = threading.Lock()
_MEMORY_CACHE: dict[str, tuple[float, float] | None] = {}
_DISK_LOADED = False


def normalize_geocode_query(address: str) -> str:
    s = unicodedata.normalize("NFKC", str(address or "")).strip()
    return "".join(s.split())


def _parse_cached_entries(raw: object) -> None:
    if not isinstance(raw, dict):
        return
    for k, v in raw.items():
        if isinstance(v, list) and len(v) == 2:
            _MEMORY_CACHE[str(k)] = (float(v[0]), float(v[1]))


def _load_disk_cache(cache_path: Path) -> None:
    global _DISK_LOADED
    if _DISK_LOADED:
        return
    with _CACHE_LOCK:
        if _DISK_LOADED:
            return
        if cache_path.exists():
            try:
                _parse_cached_entries(json.loads(cache_path.read_text(encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load GSI geocode cache from %s: %s", cache_path, e)
        _DISK_LOADED = True


def lookup_cached_coordinates(address: str, cache_path: Path | None = None) -> tuple[float, float] | None:
    """外部ネットワーク通信を行わずローカルキャッシュのみから (lat, lon) を参照する。"""
    target_path = cache_path or _DEFAULT_CACHE_PATH
    _load_disk_cache(target_path)
    key = normalize_geocode_query(address)
    return _MEMORY_CACHE.get(key) if key else None


def _extract_valid_japan_coords(items: object) -> tuple[float, float] | None:
    if not isinstance(items, list) or not items:
        return None
    geom = items[0].get("geometry") or {}
    raw_coords = geom.get("coordinates")
    if not isinstance(raw_coords, list) or len(raw_coords) < 2:
        return None
    lon, lat = float(raw_coords[0]), float(raw_coords[1])
    if 20.0 <= lat <= 46.5 and 122.0 <= lon <= 154.5:
        return (lat, lon)
    return None


def _fetch_gsi_coordinates(key: str, timeout: float) -> tuple[float, float] | None:
    try:
        resp = requests.get(GSI_GEOCODE_URL, params={"q": key}, timeout=timeout)
        if resp.status_code == 200:
            return _extract_valid_japan_coords(resp.json())
    except Exception as e:  # noqa: BLE001
        logger.debug("GSI geocode lookup failed for '%s': %s", key, e)
    return None


def _persist_cache_file(target_path: Path) -> None:
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: list(v) for k, v in _MEMORY_CACHE.items() if v is not None}
        target_path.write_text(json.dumps(serializable, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to persist GSI geocode cache: %s", e)


def geocode_address_gsi(
    address: str,
    *,
    timeout: float = 5.0,
    persist_cache: bool = False,
    cache_path: Path | None = None,
) -> tuple[float, float] | None:
    """国土地理院 AddressSearch API で住所から (latitude, longitude) を解決する（バッチ用）。"""
    key = normalize_geocode_query(address)
    if not key:
        return None

    target_path = cache_path or _DEFAULT_CACHE_PATH
    _load_disk_cache(target_path)
    if key in _MEMORY_CACHE:
        return _MEMORY_CACHE[key]

    coords = _fetch_gsi_coordinates(key, timeout)
    with _CACHE_LOCK:
        _MEMORY_CACHE[key] = coords
        if persist_cache and coords is not None:
            _persist_cache_file(target_path)

    return coords
