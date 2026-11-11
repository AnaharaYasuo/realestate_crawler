"""国土地理院ジオコーダ・5m/10m標高DEMタイル・国交省実成約/売止スプレッド一括同期スクリプト (Issue #1360)

実行内容:
1. L01/L02 地点地価座標シード ＋ DB内全物件ユニーク町丁目・街区住所の GSI AddressSearch 並列解決
2. 解決済み全座標に対する国土地理院 5mレーザDEM (`dem5a_png`) / 10m DEM (`dem_png`) タイル一括取得＆微地形算出
3. 国交省 不動産情報ライブラリ `XIT001` API（`REINFOLIB_API_KEY` 設定時）・公式CSV・L01/L02・DB掲載終了成約データの統合ベンチマーク生成
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env

setup_env.init_environment()

import realestateSettings

realestateSettings.configure()

from django.db import close_old_connections
from package.ml.features.parsers import (
    _clean_addr2,
    _extract_chome,
    _fallback_address,
    safe_float,
)
from package.ml.training.data_loader import collect_model_classes_by_type
from package.models.evaluation import LandPricePointPotential
from package.utils.gsi_dem_terrain import batch_warm_dem_cache
from package.utils.gsi_geocoder import (
    _DEFAULT_CACHE_PATH as GEOCODE_CACHE_PATH,
)
from package.utils.gsi_geocoder import (
    batch_geocode_addresses,
    lookup_cached_coordinates,
    seed_coordinate_cache,
)
from package.utils.mlit_transaction_data import (
    PREF_CODE_TO_NAME,
    build_benchmark_maps,
    fetch_reinfolib_xit001_trades,
    load_mlit_csv_or_zip_records,
    parse_mlit_trade_record,
    save_transaction_benchmarks,
)

logger = logging.getLogger(__name__)


def _seed_chome_centroids_from_land_points() -> tuple[int, list[tuple[float, float]], list[tuple[str, str, str, str, float]]]:
    """L01/L02 公的地点地価から町丁目重心座標および土地正常取引単価レコードを抽出する。"""
    chome_pts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    all_coords: list[tuple[float, float]] = []
    l01_tx_records: list[tuple[str, str, str, str, float]] = []

    qs = LandPricePointPotential.objects.values_list(
        "prefecture", "city", "chome_key", "latitude", "longitude", "land_price"
    )
    for pref, city, chome_key, lat, lon, lprice in qs.iterator(chunk_size=5000):
        if lat is not None and lon is not None:
            pt = (float(lat), float(lon))
            all_coords.append(pt)
            if chome_key:
                chome_pts[str(chome_key)].append(pt)
        if pref and city and lprice and int(lprice) > 0:
            u_man = float(lprice) / 10000.0
            ck = str(chome_key) if chome_key else f"{pref}{city}"
            l01_tx_records.append((str(pref), str(city), ck, "tochi", round(u_man, 4)))

    centroids = {
        ck: (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )
        for ck, pts in chome_pts.items()
        if pts
    }
    seeded = seed_coordinate_cache(centroids, persist=True)
    return seeded, all_coords, l01_tx_records


def _resolve_area_m2_for_model(row: dict[str, object], ptype: str) -> float:
    if ptype == "mansion":
        return float(safe_float(row.get("senyuMenseki") or row.get("tatemonoMenseki"), 0.0) or 0.0)
    if ptype == "tochi":
        return float(safe_float(row.get("tochiMenseki"), 0.0) or 0.0)
    return float(safe_float(row.get("tatemonoMenseki") or row.get("senyuMenseki"), 0.0) or 0.0)


def _extract_row_chome_and_unit_record(
    row: dict[str, object],
    ptype: str,
) -> tuple[str | None, tuple[str, str, str, str, float] | None]:
    raw_addr = str(row.get("address") or "")
    a1 = str(row.get("address1") or "")
    a2 = _clean_addr2(str(row.get("address2") or ""))
    a1, a2 = _fallback_address(raw_addr, a1, a2)
    if not a1 or not a2:
        return None, None
    chome_group = f"{a1}{a2}{_extract_chome(raw_addr, a1, a2)}"
    price_yen = float(safe_float(row.get("price"), 0.0) or 0.0)
    area_m2 = _resolve_area_m2_for_model(row, ptype)
    if price_yen <= 100_000.0 or area_m2 <= 5.0:
        return chome_group, None
    u_man = (price_yen / 10000.0) / area_m2
    if not (0.05 <= u_man <= 2500.0):
        return chome_group, None
    return chome_group, (a1, a2, chome_group, ptype, round(u_man, 4))


def _scan_single_model_rows(
    model_cls: Any,
    ptype: str,
    unique_chomes: set[str],
    closed_tx: list[tuple[str, str, str, str, float]],
    active_ask: list[tuple[str, str, str, str, float]],
) -> None:
    field_names = {f.name for f in model_cls._meta.get_fields() if hasattr(f, "attname")}
    wanted = [
        c
        for c in ("address", "address1", "address2", "price", "is_published", "senyuMenseki", "tatemonoMenseki", "tochiMenseki")
        if c in field_names
    ]
    if "price" not in wanted:
        return

    for row in model_cls.objects.values(*wanted).iterator(chunk_size=3000):
        chome_group, rec = _extract_row_chome_and_unit_record(row, ptype)
        if chome_group:
            unique_chomes.add(chome_group)
        if rec is None:
            continue
        target_list = closed_tx if row.get("is_published") is False else active_ask
        target_list.append(rec)


def _collect_db_chomes_and_price_records() -> tuple[set[str], list[tuple[str, str, str, str, float]], list[tuple[str, str, str, str, float]]]:
    models_by_type = collect_model_classes_by_type()
    unique_chomes: set[str] = set()
    closed_tx: list[tuple[str, str, str, str, float]] = []
    active_ask: list[tuple[str, str, str, str, float]] = []

    for ptype, model_entries in models_by_type.items():
        for item in model_entries:
            model_cls = item[1] if isinstance(item, tuple) else item
            try:
                _scan_single_model_rows(model_cls, ptype, unique_chomes, closed_tx, active_ask)
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping %s during open-data scan: %s", getattr(model_cls, "__name__", model_cls), e)
    return unique_chomes, closed_tx, active_ask


def _fetch_xit001_all_prefs(api_key: str, years: tuple[int, ...]) -> list[tuple[str, str, str, str, float]]:
    out: list[tuple[str, str, str, str, float]] = []
    for pref_code in sorted(PREF_CODE_TO_NAME):
        for yr in years:
            raw_list = fetch_reinfolib_xit001_trades(api_key, pref_code, yr)
            out.extend(p for p in (parse_mlit_trade_record(r) for r in raw_list) if p is not None)
    return out


def _collect_external_mlit_trades(csv_dir: Path | None, years: tuple[int, ...]) -> list[tuple[str, str, str, str, float]]:
    records: list[tuple[str, str, str, str, float]] = []
    api_key = os.environ.get("REINFOLIB_API_KEY", "").strip()
    if api_key:
        logger.info("Fetching official MLIT Reinfolib XIT001 real transactions across 47 prefectures...")
        records.extend(_fetch_xit001_all_prefs(api_key, years))
    else:
        logger.info("REINFOLIB_API_KEY not set; using L01/L02 + CSV + DB delisted/closed benchmarks.")

    target_dir = csv_dir or (Path(_crawler_root) / "data" / "mlit_csv")
    if target_dir.exists():
        csv_paths = [p for p in sorted(target_dir.glob("*")) if p.suffix.lower() in (".csv", ".zip")]
        for p in csv_paths:
            records.extend(load_mlit_csv_or_zip_records(p))
    return records


def sync_open_geo_and_transactions(
    *,
    max_workers: int = 8,
    max_geocode_queries: int = 12000,
    csv_dir: Path | None = None,
) -> dict[str, int]:
    """GSI座標・5m/10m標高DEM・国交省実成約/売止ベンチマークを一括同期する。"""
    close_old_connections()
    seeded_cnt, l01_coords, l01_tx = _seed_chome_centroids_from_land_points()
    unique_chomes, closed_tx, active_ask = _collect_db_chomes_and_price_records()

    sorted_chomes = sorted(unique_chomes)[:max_geocode_queries]
    geocoded_cnt = batch_geocode_addresses(sorted_chomes, max_workers=max_workers)
    logger.info(
        "GSI Geocode Sync: seeded=%d from L01/L02, newly_resolved=%d (unique_chomes=%d)",
        seeded_cnt,
        geocoded_cnt,
        len(unique_chomes),
    )

    dem_coords: list[tuple[float, float]] = list(l01_coords)
    for ch in unique_chomes:
        pt = lookup_cached_coordinates(ch, cache_path=GEOCODE_CACHE_PATH)
        if pt is not None:
            dem_coords.append(pt)
    dem_warmed = batch_warm_dem_cache(dem_coords, max_workers=max_workers)
    logger.info("GSI DEM Terrain Sync: warmed=%d new 11m grid cells (total input coords=%d)", dem_warmed, len(dem_coords))

    ext_tx = _collect_external_mlit_trades(csv_dir=csv_dir, years=(2024, 2025))
    all_tx = ext_tx + l01_tx + closed_tx
    if not all_tx and active_ask:
        all_tx = [(p, c, ch, pt, round(u * 0.93, 4)) for p, c, ch, pt, u in active_ask]

    bench_payload = build_benchmark_maps(all_tx, asking_records=active_ask)
    out_path = save_transaction_benchmarks(bench_payload)
    logger.info(
        "Transaction Benchmark Sync saved to %s (chome=%d, city=%d, pref=%d)",
        out_path,
        len(bench_payload["chome"]),
        len(bench_payload["city"]),
        len(bench_payload["pref"]),
    )
    close_old_connections()
    return {
        "seeded_chomes": seeded_cnt,
        "geocoded_chomes": geocoded_cnt,
        "dem_cells_warmed": dem_warmed,
        "tx_chome_benchmarks": len(bench_payload["chome"]),
        "tx_city_benchmarks": len(bench_payload["city"]),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Sync GSI coordinates, GSI 5m/10m DEM terrain, and MLIT transaction benchmarks")
    parser.add_argument("--workers", type=int, default=8, help="Parallel HTTP workers for GSI APIs")
    parser.add_argument("--max-geocode", type=int, default=12000, help="Max uncached chome queries per run")
    parser.add_argument("--csv-dir", type=str, default=None, help="Optional directory containing MLIT Reinfolib CSV/ZIP files")
    args = parser.parse_args()
    sync_open_geo_and_transactions(
        max_workers=args.workers,
        max_geocode_queries=args.max_geocode,
        csv_dir=Path(args.csv_dir) if args.csv_dir else None,
    )


if __name__ == "__main__":
    main()
