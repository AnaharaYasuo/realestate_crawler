# -*- coding: utf-8 -*-
"""
外部データ一括同期・洗い替えランナー (scripts/sync_all_potentials.py)

e-Stat（市区町村別所得・人口動態）、国土交通省（駅別乗降人員）、
および地価公示（用途別平均平米単価）の基礎データを1コマンドで一括同期・洗い替えます。
自然キー（自治体名・駅名・地名）による動的結合により、マスタ洗い替え後も既存物件との結合を完全に維持します。
"""
import os
import sys
import logging
import argparse

_crawler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from scripts.data_import.sync_estat_municipalities import sync_municipalities
from scripts.data_import.import_mlit_stations import import_mlit_stations, generate_sample_mlit_csv
from scripts.data_import.import_mlit_land_prices import import_land_prices, generate_sample_land_price_csv
from scripts.data_import.import_hazard_and_urban_zones import import_hazard_map, import_urban_planning_zones
from package.models.evaluation import (
    MunicipalPotential, StationPotential, LandPricePotential,
    HazardMapPotential, UrbanPlanningZonePotential
)

logger = logging.getLogger(__name__)


def run_all_syncs(estat_csv=None, stations_csv=None, land_prices_csv=None,
                  hazard_map_csv=None, urban_zones_csv=None,
                  skip_estat=False, skip_stations=False, skip_land_prices=False,
                  skip_hazard_map=False, skip_urban_zones=False):
    """
    全外部ポテンシャルデータを一括同期・洗い替えする。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    temp_files_to_cleanup = []

    results = {
        "estat": {"status": "skipped" if skip_estat else "pending", "count": 0},
        "stations": {"status": "skipped" if skip_stations else "pending", "count": 0},
        "land_prices": {"status": "skipped" if skip_land_prices else "pending", "count": 0},
        "hazard_map": {"status": "skipped" if skip_hazard_map else "pending", "count": 0},
        "urban_zones": {"status": "skipped" if skip_urban_zones else "pending", "count": 0},
    }

    try:
        # 1. e-Stat 自治体ポテンシャル同期
        if not skip_estat:
            logger.info("=" * 60)
            logger.info("Step 1/5: Syncing e-Stat Municipal Potential...")
            logger.info("=" * 60)
            sync_municipalities(csv_path=estat_csv)
            m_count = MunicipalPotential.objects.count()
            results["estat"]["status"] = "success"
            results["estat"]["count"] = m_count
            logger.info(f"e-Stat Sync Complete: Total MunicipalPotential records = {m_count}")

        # 2. 国土交通省 駅別乗降客数同期
        if not skip_stations:
            logger.info("=" * 60)
            logger.info("Step 2/5: Syncing MLIT Station Passenger Volume...")
            logger.info("=" * 60)
            target_station_csv = stations_csv
            if not target_station_csv or not os.path.exists(target_station_csv):
                temp_station_csv = os.path.join(current_dir, "temp_mlit_stations_sync.csv")
                generate_sample_mlit_csv(temp_station_csv)
                target_station_csv = temp_station_csv
                temp_files_to_cleanup.append(temp_station_csv)

            import_mlit_stations(target_station_csv)
            s_count = StationPotential.objects.count()
            results["stations"]["status"] = "success"
            results["stations"]["count"] = s_count
            logger.info(f"MLIT Stations Sync Complete: Total StationPotential records = {s_count}")

        # 3. 国土交通省 地価公示同期
        if not skip_land_prices:
            logger.info("=" * 60)
            logger.info("Step 3/5: Syncing MLIT Land Prices...")
            logger.info("=" * 60)
            target_land_csv = land_prices_csv
            if not target_land_csv or not os.path.exists(target_land_csv):
                temp_land_csv = os.path.join(current_dir, "temp_mlit_land_prices_sync.csv")
                generate_sample_land_price_csv(temp_land_csv)
                target_land_csv = temp_land_csv
                temp_files_to_cleanup.append(temp_land_csv)

            import_land_prices(target_land_csv)
            lp_count = LandPricePotential.objects.count()
            results["land_prices"]["status"] = "success"
            results["land_prices"]["count"] = lp_count
            logger.info(f"MLIT Land Prices Sync Complete: Total LandPricePotential records = {lp_count}")

        # 4. 国土数値情報 ハザードマップ（浸水・土砂リスク）同期
        if not skip_hazard_map:
            logger.info("=" * 60)
            logger.info("Step 4/5: Syncing MLIT Hazard Maps (Flood & Landslide)...")
            logger.info("=" * 60)
            h_count = import_hazard_map(hazard_map_csv)
            results["hazard_map"]["status"] = "success"
            results["hazard_map"]["count"] = h_count
            logger.info(f"Hazard Maps Sync Complete: Total HazardMapPotential records = {h_count}")

        # 5. 都市計画法 用途地域規制マスタ同期
        if not skip_urban_zones:
            logger.info("=" * 60)
            logger.info("Step 5/5: Syncing Urban Planning Zones (Kenpei & Youseki)...")
            logger.info("=" * 60)
            z_count = import_urban_planning_zones(urban_zones_csv)
            results["urban_zones"]["status"] = "success"
            results["urban_zones"]["count"] = z_count
            logger.info(f"Urban Planning Zones Sync Complete: Total UrbanPlanningZonePotential records = {z_count}")

        logger.info("=" * 60)
        logger.info("All External Potentials Sync Succeeded!")
        logger.info(f"Summary: Municipal={results['estat']['count']}, Stations={results['stations']['count']}, "
                    f"LandPrices={results['land_prices']['count']}, HazardMaps={results['hazard_map']['count']}, "
                    f"UrbanZones={results['urban_zones']['count']}")
        logger.info("=" * 60)
        return results

    finally:
        for tmp in temp_files_to_cleanup:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                    logger.info(f"Cleaned up temp file: {tmp}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp}: {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Sync all external potential datasets (e-Stat, Stations, Land Prices, Hazard, Zones)")
    parser.add_argument("--estat-csv", default=None, help="Path to e-Stat municipal CSV")
    parser.add_argument("--stations-csv", default=None, help="Path to MLIT station passenger volume CSV")
    parser.add_argument("--land-prices-csv", default=None, help="Path to MLIT land prices CSV")
    parser.add_argument("--hazard-map-csv", default=None, help="Path to Hazard Map CSV")
    parser.add_argument("--urban-zones-csv", default=None, help="Path to Urban Planning Zones CSV")
    parser.add_argument("--skip-estat", action="store_true", help="Skip e-Stat synchronization")
    parser.add_argument("--skip-stations", action="store_true", help="Skip MLIT stations synchronization")
    parser.add_argument("--skip-land-prices", action="store_true", help="Skip MLIT land prices synchronization")
    parser.add_argument("--skip-hazard-map", action="store_true", help="Skip Hazard Map synchronization")
    parser.add_argument("--skip-urban-zones", action="store_true", help="Skip Urban Planning Zones synchronization")

    args = parser.parse_args()
    run_all_syncs(
        estat_csv=args.estat_csv,
        stations_csv=args.stations_csv,
        land_prices_csv=args.land_prices_csv,
        hazard_map_csv=args.hazard_map_csv,
        urban_zones_csv=args.urban_zones_csv,
        skip_estat=args.skip_estat,
        skip_stations=args.skip_stations,
        skip_land_prices=args.skip_land_prices,
        skip_hazard_map=args.skip_hazard_map,
        skip_urban_zones=args.skip_urban_zones,
    )


if __name__ == "__main__":
    main()

