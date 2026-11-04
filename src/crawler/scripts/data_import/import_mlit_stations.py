# -*- coding: utf-8 -*-
"""
国土交通省 国土数値情報（駅別乗降客数 S12）全国全駅（約9,300駅）高速バルクインポート・同期モジュール
(scripts/data_import/import_mlit_stations.py)

国土交通省「国土数値情報 駅別乗降客数データ（S12）」の公式GeoJSONデータを自動ダウンロード・パースし、
全国全駅（JR・私鉄・地下鉄・第三セクター等）の実績乗降客数をDB（station_potential）に
ON DUPLICATE KEY UPDATE による高速バルクSQLで一括同期・洗い替えします。
"""
import io
import json
import logging
import os
import sys
import zipfile
import requests
from django.db import connection

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import StationPotential

logger = logging.getLogger(__name__)

MLIT_STATION_ZIP_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/S12/S12-22/S12-22_GML.zip"


def download_and_extract_mlit_stations(url: str = MLIT_STATION_ZIP_URL, timeout: int = 90) -> list[dict]:
    logger.info("Downloading MLIT Station Passenger Volume data from %s...", url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    logger.info("Downloaded %d bytes. Extracting GeoJSON...", len(resp.content))

    stations = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        geojson_name = None
        for name in z.namelist():
            if name.endswith("NumberOfPassengers.geojson"):
                if "UTF-8" in name:
                    geojson_name = name
                    break
                geojson_name = name

        if not geojson_name:
            raise FileNotFoundError("Station GeoJSON file not found in downloaded MLIT archive.")

        logger.info("Reading GeoJSON: %s...", geojson_name)
        content = z.read(geojson_name)
        
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("cp932", errors="replace").replace("\\", "\\\\")

        data = json.loads(text)
        features = data.get("features", [])
        logger.info("Total raw station features in GeoJSON: %d", len(features))

        station_map = {}
        for f in features:
            props = f.get("properties", {})
            st_name = props.get("S12_001")
            corp_name = props.get("S12_002")
            line_name = props.get("S12_003")
            vol = props.get("S12_049")

            if not st_name:
                continue

            st_clean = str(st_name).strip().replace("駅", "")
            line_clean = f"{corp_name or ''} {line_name or ''}".strip()
            
            try:
                volume = int(vol) if vol is not None else 0
            except (ValueError, TypeError):
                volume = 0

            key = (st_clean, line_clean)
            if key not in station_map or volume > station_map[key]:
                station_map[key] = volume

        for (st_clean, line_clean), vol in station_map.items():
            stations.append({
                "station_name": st_clean,
                "railway_line": line_clean,
                "passenger_volume": vol,
            })

    logger.info("Aggregated into %d unique station/line pairs.", len(stations))
    return stations


def import_mlit_stations(csv_path: str = None) -> int:
    logger.info("Starting synchronization of nationwide MLIT station potentials...")
    stations = download_and_extract_mlit_stations()
    if not stations:
        raise RuntimeError("No station records extracted from MLIT data source.")

    sql = """
    INSERT INTO station_potential (station_name, railway_line, passenger_volume)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE passenger_volume = VALUES(passenger_volume)
    """

    params = [
        (s["station_name"], s["railway_line"], s["passenger_volume"])
        for s in stations
    ]

    logger.info("Executing bulk insert with ON DUPLICATE KEY UPDATE (%d rows)...", len(params))
    chunk_size = 2000
    with connection.cursor() as cursor:
        for i in range(0, len(params), chunk_size):
            chunk = params[i:i + chunk_size]
            cursor.executemany(sql, chunk)

    total = StationPotential.objects.count()
    logger.info("✅ MLIT Station passenger volume bulk sync complete: Total in DB = %d", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import_mlit_stations()
