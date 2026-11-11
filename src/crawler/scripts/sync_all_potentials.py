"""
外部データ一括同期および洗い替えランナー (scripts/sync_all_potentials.py)

国交省・総務省・社人研等の公式オープンデータ（API/ダウンロード）から全国全自治体・全駅・全地点の
統計・地理・マスターデータを並列（ThreadPoolExecutor）で取得・投入し、本番DBに一括登録・洗い替え（upsert）します。
"""
import argparse
import datetime
import logging
import os
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

_crawler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env

setup_env.init_environment()

import realestateSettings

realestateSettings.configure()

from django.db import close_old_connections
from django.utils import timezone
from package.models.building_master import BuildingMaster
from package.models.evaluation import (
    CapRateBenchmarkPotential,
    HazardMapPotential,
    LandPricePointPotential,
    MacroEconomicIndex,
    MunicipalFuturePotential,
    MunicipalPotential,
    MunicipalYearlyPotential,
    StationPotential,
    UrbanInductionZoneMaster,
    UrbanPlanningZonePotential,
)
from scripts.data_import.generate_building_master import (
    generate_and_sync_building_master,
)
from scripts.data_import.import_hazard_and_urban_zones import (
    import_hazard_map,
    import_urban_planning_zones,
)
from scripts.data_import.import_ipss_future_population import (
    sync_ipss_future_population,
)
from scripts.data_import.import_mlit_land_prices import import_land_prices
from scripts.data_import.import_mlit_stations import import_mlit_stations
from scripts.data_import.import_urban_induction_zones import sync_urban_induction_zones
from scripts.data_import.sync_estat_municipalities import sync_municipalities
from scripts.data_import.sync_macro_economic_indices import sync_macro_economic_indices
from scripts.data_import.sync_mlit_open_geo_and_transactions import (
    sync_open_geo_and_transactions,
)
from scripts.data_import.sync_rent_and_cap_rate_potentials import (
    sync_rent_and_cap_rate_potentials,
)
from scripts.data_import.sync_yearly_historical_potentials import (
    sync_municipal_yearly_potentials,
    sync_station_yearly_potentials,
)

logger = logging.getLogger(__name__)


def _is_macro_fresh(today: datetime.date | None = None) -> bool:
    """当月（YYYY-MM）の `MacroEconomicIndex` レコードが既に存在するか判定する。"""
    d = today or datetime.date.today()
    ym = f"{d.year:04d}-{d.month:02d}"
    return MacroEconomicIndex.objects.filter(year_month=ym).exists()


def _has_min_rows(model_cls: Any, min_rows: int) -> bool:
    try:
        return model_cls.objects.count() >= min_rows
    except Exception:  # noqa: BLE001
        return False


def _is_updated_within_days(model_cls: Any, max_age_days: int, min_rows: int = 100) -> bool:
    try:
        if model_cls.objects.count() < min_rows:
            return False
        cutoff = timezone.now() - datetime.timedelta(days=max_age_days)
        return model_cls.objects.filter(updated_at__gte=cutoff).exists()
    except Exception:  # noqa: BLE001
        return False


def _resolve_effective_skip_flags(raw_flags: dict[str, bool], respect_ttl: bool, force: bool) -> dict[str, bool]:
    flags = dict(raw_flags)
    if force:
        return dict.fromkeys(flags, False)
    if not respect_ttl:
        return flags

    ttl_checks: dict[str, Callable[[], bool]] = {
        "estat": lambda: _has_min_rows(MunicipalPotential, 1500),
        "stations": lambda: _has_min_rows(StationPotential, 5000),
        "urban_zones": lambda: _has_min_rows(UrbanPlanningZonePotential, 10),
        "land_prices": lambda: _is_updated_within_days(LandPricePointPotential, max_age_days=14, min_rows=20000),
        "hazard_map": lambda: _has_min_rows(HazardMapPotential, 1500),
        "future_pop": lambda: _has_min_rows(MunicipalFuturePotential, 5000),
        "induction_zones": lambda: _has_min_rows(UrbanInductionZoneMaster, 500),
        "historical": lambda: _has_min_rows(MunicipalYearlyPotential, 5000),
        "building_master": lambda: _is_updated_within_days(BuildingMaster, max_age_days=7, min_rows=500),
        "rent_cap_rates": lambda: _is_updated_within_days(CapRateBenchmarkPotential, max_age_days=7, min_rows=50),
        "macro": _is_macro_fresh,
    }
    for key, checker in ttl_checks.items():
        if not flags.get(key, False) and checker():
            logger.info("⏩ [TTL Fresh] Skipping '%s' sync (already populated and within TTL).", key)
            flags[key] = True
    return flags


def _execute_parallel_sync_phase(
    phase_label: str,
    tasks: list[tuple[str, Callable[..., Any]]],
    max_workers: int,
    results: dict[str, Any],
) -> None:
    if not tasks:
        return
    logger.info("=" * 60)
    logger.info("%s: Running %d tasks in parallel (workers=%d)...", phase_label, len(tasks), max_workers)
    logger.info("=" * 60)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {executor.submit(func): name for name, func in tasks}
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                cnt = fut.result()
                results[name] = {"status": "success", "count": cnt}
                logger.info("✅ %s Task '%s' completed: %s records", phase_label, name, cnt)
            except Exception as e:
                logger.exception("❌ %s Task '%s' failed", phase_label, name)
                results[name] = {"status": "error", "error": str(e)}


def _build_derived_sync_tasks(
    skip_flags: dict[str, bool],
    live_crawl_rent: bool,
) -> list[tuple[str, Callable[..., Any]]]:
    specs: list[tuple[bool, str, Callable[..., Any]]] = [
        (skip_flags["land_prices"], "land_prices", import_land_prices),
        (skip_flags["hazard_map"], "hazard_map", import_hazard_map),
        (skip_flags["future_pop"], "future_population", sync_ipss_future_population),
        (skip_flags["induction_zones"], "urban_induction_zones", sync_urban_induction_zones),
        (skip_flags["historical"], "muni_yearly", sync_municipal_yearly_potentials),
        (skip_flags["historical"], "station_yearly", sync_station_yearly_potentials),
        (skip_flags["building_master"], "building_master", generate_and_sync_building_master),
        (skip_flags["macro"], "macro_economic_indices", sync_macro_economic_indices),
        (
            skip_flags["rent_cap_rates"],
            "rent_and_cap_rates",
            lambda: sync_rent_and_cap_rate_potentials(enable_live_crawl=live_crawl_rent),
        ),
    ]
    return [(name, fn) for skipped, name, fn in specs if not skipped]


def run_all_syncs(
    skip_estat: bool = False,
    skip_stations: bool = False,
    skip_land_prices: bool = False,
    skip_hazard_map: bool = False,
    skip_urban_zones: bool = False,
    skip_future_pop: bool = False,
    skip_induction_zones: bool = False,
    skip_historical: bool = False,
    skip_building_master: bool = False,
    skip_rent_cap_rates: bool = False,
    skip_macro: bool = False,
    skip_open_geo_tx: bool = False,
    live_crawl_rent: bool = False,
    respect_ttl: bool = False,
    force: bool = False,
    max_workers: int = 4,
) -> dict:
    """
    全外部ポテンシャルデータおよびマスターデータ（全14種）を並列一括同期・洗い替えする。
    """
    results: dict[str, Any] = {}
    close_old_connections()

    eff = _resolve_effective_skip_flags(
        {
            "estat": skip_estat,
            "stations": skip_stations,
            "urban_zones": skip_urban_zones,
            "land_prices": skip_land_prices,
            "hazard_map": skip_hazard_map,
            "future_pop": skip_future_pop,
            "induction_zones": skip_induction_zones,
            "historical": skip_historical,
            "building_master": skip_building_master,
            "rent_cap_rates": skip_rent_cap_rates,
            "macro": skip_macro,
            "open_geo_tx": skip_open_geo_tx,
        },
        respect_ttl=respect_ttl,
        force=force,
    )

    base_specs: list[tuple[bool, str, Callable[..., Any]]] = [
        (eff["estat"], "municipalities", sync_municipalities),
        (eff["stations"], "stations", import_mlit_stations),
        (eff["urban_zones"], "urban_zones", import_urban_planning_zones),
    ]
    base_tasks = [(name, fn) for skipped, name, fn in base_specs if not skipped]
    _execute_parallel_sync_phase("Phase 1", base_tasks, max_workers, results)

    close_old_connections()
    derived_tasks = _build_derived_sync_tasks(eff, live_crawl_rent)
    _execute_parallel_sync_phase("Phase 2", derived_tasks, max_workers, results)

    if not eff["open_geo_tx"]:
        close_old_connections()
        try:
            geo_res = sync_open_geo_and_transactions(max_workers=max(4, max_workers))
            results["open_geo_and_transactions"] = {"status": "success", "count": geo_res}
            logger.info("✅ Phase 3 Task 'open_geo_and_transactions' completed: %s", geo_res)
        except Exception as e:
            logger.exception("❌ Phase 3 Task 'open_geo_and_transactions' failed")
            results["open_geo_and_transactions"] = {"status": "error", "error": str(e)}

    close_old_connections()
    logger.info("=" * 60)
    logger.info("🎉 Parallel External Potentials & Masters Synchronization Finished!")
    logger.info("=" * 60)
    return results


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Sync all external potential datasets nationwide in parallel")
    parser.add_argument("--workers", type=int, default=4, help="Max parallel workers")
    parser.add_argument("--skip-estat", action="store_true", help="Skip municipal income/pop sync")
    parser.add_argument("--skip-stations", action="store_true", help="Skip MLIT stations sync")
    parser.add_argument("--skip-land-prices", action="store_true", help="Skip MLIT land prices sync")
    parser.add_argument("--skip-hazard-map", action="store_true", help="Skip hazard maps sync")
    parser.add_argument("--skip-urban-zones", action="store_true", help="Skip urban planning zones sync")
    parser.add_argument("--skip-future-pop", action="store_true", help="Skip future population sync")
    parser.add_argument("--skip-induction-zones", action="store_true", help="Skip induction zones sync")
    parser.add_argument("--skip-historical", action="store_true", help="Skip historical potentials sync")
    parser.add_argument("--skip-building-master", action="store_true", help="Skip building master sync")
    parser.add_argument("--skip-rent-cap-rates", action="store_true", help="Skip rent market and cap-rate sync")
    parser.add_argument("--skip-macro", action="store_true", help="Skip MacroEconomicIndex sync")
    parser.add_argument("--skip-open-geo-tx", action="store_true", help="Skip GSI geocode/DEM and MLIT transaction sync")
    parser.add_argument("--live-crawl-rent", action="store_true", help="Enable live portal crawling for rent/cap-rate")
    parser.add_argument("--respect-ttl", action="store_true", help="Skip static/periodic masters already populated within TTL")
    parser.add_argument("--force", action="store_true", help="Force full refresh overriding TTL checks")

    args = parser.parse_args()
    run_all_syncs(
        skip_estat=args.skip_estat,
        skip_stations=args.skip_stations,
        skip_land_prices=args.skip_land_prices,
        skip_hazard_map=args.skip_hazard_map,
        skip_urban_zones=args.skip_urban_zones,
        skip_future_pop=args.skip_future_pop,
        skip_induction_zones=args.skip_induction_zones,
        skip_historical=args.skip_historical,
        skip_building_master=args.skip_building_master,
        skip_rent_cap_rates=args.skip_rent_cap_rates,
        skip_macro=args.skip_macro,
        skip_open_geo_tx=args.skip_open_geo_tx,
        live_crawl_rent=args.live_crawl_rent,
        respect_ttl=args.respect_ttl,
        force=args.force,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
