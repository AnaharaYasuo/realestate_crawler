# -*- coding: utf-8 -*-
"""
外部データ一括同期および洗い替えランナー (scripts/sync_all_potentials.py)

国交省・総務省・社人研等の公式オープンデータ（API/ダウンロード）から全国全自治体・全駅・全地点の
統計・地理・マスターデータを並列（ThreadPoolExecutor）で取得・投入し、本番DBに一括登録・洗い替え（upsert）します。
"""
import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_crawler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from django.db import close_old_connections

from scripts.data_import.sync_estat_municipalities import sync_municipalities
from scripts.data_import.import_mlit_stations import import_mlit_stations
from scripts.data_import.import_mlit_land_prices import import_land_prices
from scripts.data_import.import_hazard_and_urban_zones import import_hazard_map, import_urban_planning_zones
from scripts.data_import.import_ipss_future_population import sync_ipss_future_population
from scripts.data_import.import_urban_induction_zones import sync_urban_induction_zones
from scripts.data_import.sync_yearly_historical_potentials import sync_municipal_yearly_potentials, sync_station_yearly_potentials
from scripts.data_import.generate_building_master import generate_and_sync_building_master

logger = logging.getLogger(__name__)


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
    max_workers: int = 4,
) -> dict:
    """
    全外部ポテンシャルデータおよびマスターデータを並列一括同期・洗い替えする。
    """
    results = {}
    close_old_connections()

    # Step 1: 基礎マスター（自治体マクロ・駅・用途地域）を並列同期
    base_tasks = []
    if not skip_estat:
        base_tasks.append(("municipalities", sync_municipalities))
    if not skip_stations:
        base_tasks.append(("stations", import_mlit_stations))
    if not skip_urban_zones:
        base_tasks.append(("urban_zones", import_urban_planning_zones))

    if base_tasks:
        logger.info("=" * 60)
        logger.info(f"Phase 1: Running {len(base_tasks)} base master tasks in parallel (workers={max_workers})...")
        logger.info("=" * 60)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(func): name for name, func in base_tasks
            }
            for fut in as_completed(future_to_name):
                name = future_to_name[fut]
                try:
                    cnt = fut.result()
                    results[name] = {"status": "success", "count": cnt}
                    logger.info(f"✅ Phase 1 Task '{name}' completed: {cnt} records")
                except Exception as e:
                    logger.exception(f"❌ Phase 1 Task '{name}' failed: {e}")
                    results[name] = {"status": "error", "error": str(e)}

    # Step 2: 自治体・駅マスターに依存する派生統計を並列同期
    close_old_connections()
    derived_tasks = []
    if not skip_land_prices:
        derived_tasks.append(("land_prices", import_land_prices))
    if not skip_hazard_map:
        derived_tasks.append(("hazard_map", import_hazard_map))
    if not skip_future_pop:
        derived_tasks.append(("future_population", sync_ipss_future_population))
    if not skip_induction_zones:
        derived_tasks.append(("urban_induction_zones", sync_urban_induction_zones))
    if not skip_historical:
        derived_tasks.append(("muni_yearly", sync_municipal_yearly_potentials))
        derived_tasks.append(("station_yearly", sync_station_yearly_potentials))
    if not skip_building_master:
        derived_tasks.append(("building_master", generate_and_sync_building_master))

    if derived_tasks:
        logger.info("=" * 60)
        logger.info(f"Phase 2: Running {len(derived_tasks)} derived statistical tasks in parallel (workers={max_workers})...")
        logger.info("=" * 60)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(func): name for name, func in derived_tasks
            }
            for fut in as_completed(future_to_name):
                name = future_to_name[fut]
                try:
                    cnt = fut.result()
                    results[name] = {"status": "success", "count": cnt}
                    logger.info(f"✅ Phase 2 Task '{name}' completed: {cnt} records")
                except Exception as e:
                    logger.exception(f"❌ Phase 2 Task '{name}' failed: {e}")
                    results[name] = {"status": "error", "error": str(e)}

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
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
