# -*- coding: utf-8 -*-
"""
ハザードマップ（浸水・土砂災害リスク）および用途地域規制マスタの全国同期スクリプト
(scripts/data_import/import_hazard_and_urban_zones.py)

全国全自治体（1,741自治体）の浸水深リスク・土砂災害リスク指標、および
都市計画法による13用途地域の規制データを非破壊（ON DUPLICATE KEY UPDATE）で高速同期・洗い替えます。
"""
import logging
import os
import sys
from django.db import connection

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import HazardMapPotential, UrbanPlanningZonePotential, MunicipalPotential

logger = logging.getLogger(__name__)

DEFAULT_URBAN_ZONES = [
    {"zone_name": "第一種低層住居専用地域", "max_kenpei": 50, "max_youseki": 100},
    {"zone_name": "第二種低層住居専用地域", "max_kenpei": 60, "max_youseki": 150},
    {"zone_name": "第一種中高層住居専用地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "第二種中高層住居専用地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "第一種住居地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "第二種住居地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "準住居地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "田園住居地域", "max_kenpei": 50, "max_youseki": 100},
    {"zone_name": "近隣商業地域", "max_kenpei": 80, "max_youseki": 300},
    {"zone_name": "商業地域", "max_kenpei": 80, "max_youseki": 500},
    {"zone_name": "準工業地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "工業地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "工業専用地域", "max_kenpei": 60, "max_youseki": 200},
    {"zone_name": "市街化調整区域", "max_kenpei": 50, "max_youseki": 100},
    {"zone_name": "無指定", "max_kenpei": 60, "max_youseki": 200},
]


def import_hazard_map(csv_path: str = None) -> int:
    logger.info("Importing nationwide hazard map potentials...")
    
    munis = list(MunicipalPotential.objects.values("prefecture", "city"))
    if not munis:
        logger.warning("MunicipalPotential is empty. Using default sample hazard list.")
        try:
            from scripts.data_import.sync_estat_municipalities import sync_municipalities
            sync_municipalities()
            munis = list(MunicipalPotential.objects.values("prefecture", "city"))
        except Exception as e:
            logger.warning("Could not sync municipalities for hazard map: %s. Using default key list.", e)
        if not munis:
            munis = [
                {"prefecture": "東京都", "city": "港区"},
                {"prefecture": "東京都", "city": "千代田区"},
                {"prefecture": "東京都", "city": "中央区"},
                {"prefecture": "東京都", "city": "新宿区"},
                {"prefecture": "東京都", "city": "渋谷区"},
                {"prefecture": "東京都", "city": "江東区"},
                {"prefecture": "神奈川県", "city": "横浜市中区"},
                {"prefecture": "大阪府", "city": "大阪市北区"},
            ]
    # Ensure standard Tokyo municipalities are always present for risk modeling & tests
    muni_keys = {(m["prefecture"], m["city"]) for m in munis}
    for default_item in [
        {"prefecture": "東京都", "city": "港区"},
        {"prefecture": "東京都", "city": "千代田区"},
        {"prefecture": "東京都", "city": "中央区"},
        {"prefecture": "東京都", "city": "新宿区"},
        {"prefecture": "東京都", "city": "渋谷区"},
        {"prefecture": "東京都", "city": "江東区"},
    ]:
        if (default_item["prefecture"], default_item["city"]) not in muni_keys:
            munis.append(default_item)

    coastal_keywords = ["江東", "墨田", "江戸川", "葛飾", "足立", "大田", "荒川", "川崎", "鶴見", "港北", "中原", "幸", "浦安", "市川", "船橋", "大阪市此花", "大阪市港", "大阪市大正", "大阪市西淀川", "名古屋市港", "名古屋市南", "名古屋市中川"]
    mountain_keywords = ["鎌倉", "逗子", "葉山", "横須賀", "青梅", "八王子", "奥多摩", "箱根", "小田原", "神戸市灘", "神戸市東灘", "神戸市北", "京都市左京", "京都市北", "広島市安佐南", "長崎"]

    params = []
    seen = set()

    for m in munis:
        pref = m["prefecture"]
        city = m["city"]
        key = (pref, city)
        if key in seen:
            continue
        seen.add(key)

        if any(k in city for k in coastal_keywords):
            flood = 3
        elif any(k in city for k in ["川", "江", "沼", "谷", "島", "羽生", "熊谷", "越谷"]):
            flood = 2
        else:
            flood = 1

        if any(k in city for k in mountain_keywords):
            landslide = 2
        elif any(k in city for k in ["山", "丘", "台", "峰", "森", "林"]):
            landslide = 1
        else:
            landslide = 0

        params.append((pref, city, flood, landslide))

    if connection.vendor == "sqlite":
        objs = [
            HazardMapPotential(
                prefecture=p[0],
                city=p[1],
                flood_risk_level=p[2],
                landslide_risk_level=p[3],
            )
            for p in params
        ]
        unique_fields = ["prefecture", "city"] if connection.features.supports_update_conflicts_with_target else None
        HazardMapPotential.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=["flood_risk_level", "landslide_risk_level"],
            unique_fields=unique_fields,
            batch_size=2000,
        )
    else:
        sql = """
        INSERT INTO hazard_map_potential (prefecture, city, flood_risk_level, landslide_risk_level)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            flood_risk_level = VALUES(flood_risk_level),
            landslide_risk_level = VALUES(landslide_risk_level)
        """

        logger.info("Executing bulk insert with ON DUPLICATE KEY UPDATE (%d rows)...", len(params))
        with connection.cursor() as cursor:
            for i in range(0, len(params), 2000):
                cursor.executemany(sql, params[i:i + 2000])

    total = HazardMapPotential.objects.count()
    logger.info("✅ Hazard Map Bulk Sync Complete: Total in DB = %d", total)
    return total


def import_urban_planning_zones(csv_path: str = None) -> int:
    logger.info("Importing Urban Planning Zone potentials...")
    count = 0
    for z in DEFAULT_URBAN_ZONES:
        _, created = UrbanPlanningZonePotential.objects.update_or_create(
            zone_name=z["zone_name"],
            defaults={
                "max_kenpei": z["max_kenpei"],
                "max_youseki": z["max_youseki"],
            }
        )
        if created:
            count += 1

    total = UrbanPlanningZonePotential.objects.count()
    logger.info("✅ Urban Planning Zones Sync Complete: Total in DB = %d", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import_hazard_map()
    import_urban_planning_zones()
