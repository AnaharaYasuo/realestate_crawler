# -*- coding: utf-8 -*-
"""
ハザードマップ（浸水・土砂災害リスク）および用途地域規制マスタのインポートスクリプト
(scripts/data_import/import_hazard_and_urban_zones.py)

国交省国土数値情報（洪水浸水想定区域 A31・土砂災害警戒区域 A33）統計および
都市計画法用途地域規制データを非破壊（update_or_create）で同期・洗い替えます。
"""
import os
import sys
import csv
import logging

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import HazardMapPotential, UrbanPlanningZonePotential

logger = logging.getLogger(__name__)

# 都市計画法による標準13用途地域＋調整区域等の建ぺい・容積率マスタ
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

# 主要市区町村のハザードマップ（浸水深レベル: 0〜4, 土砂災害リスク: 0〜2）代表サンプル
DEFAULT_HAZARD_DATA = [
    # 東京都23区
    {"prefecture": "東京都", "city": "千代田区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "中央区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "港区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "新宿区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "文京区", "flood_risk_level": 1, "landslide_risk_level": 1},
    {"prefecture": "東京都", "city": "台東区", "flood_risk_level": 3, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "墨田区", "flood_risk_level": 4, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "江東区", "flood_risk_level": 4, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "品川区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "目黒区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "大田区", "flood_risk_level": 3, "landslide_risk_level": 1},
    {"prefecture": "東京都", "city": "世田谷区", "flood_risk_level": 1, "landslide_risk_level": 1},
    {"prefecture": "東京都", "city": "渋谷区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "中野区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "杉並区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "豊島区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "北区", "flood_risk_level": 3, "landslide_risk_level": 1},
    {"prefecture": "東京都", "city": "荒川区", "flood_risk_level": 4, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "板橋区", "flood_risk_level": 2, "landslide_risk_level": 1},
    {"prefecture": "東京都", "city": "練馬区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "足立区", "flood_risk_level": 4, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "葛飾区", "flood_risk_level": 4, "landslide_risk_level": 0},
    {"prefecture": "東京都", "city": "江戸川区", "flood_risk_level": 4, "landslide_risk_level": 0},
    # 神奈川県
    {"prefecture": "神奈川県", "city": "横浜市中区", "flood_risk_level": 2, "landslide_risk_level": 1},
    {"prefecture": "神奈川県", "city": "横浜市西区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "神奈川県", "city": "川崎市中原区", "flood_risk_level": 3, "landslide_risk_level": 0},
    {"prefecture": "神奈川県", "city": "鎌倉市", "flood_risk_level": 2, "landslide_risk_level": 2},
    # 埼玉県
    {"prefecture": "埼玉県", "city": "さいたま市大宮区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "埼玉県", "city": "川口市", "flood_risk_level": 3, "landslide_risk_level": 0},
    # 千葉県
    {"prefecture": "千葉県", "city": "千葉市中央区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "千葉県", "city": "浦安市", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "千葉県", "city": "船橋市", "flood_risk_level": 2, "landslide_risk_level": 0},
    # 大阪府
    {"prefecture": "大阪府", "city": "大阪市北区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "大阪府", "city": "大阪市中央区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "大阪府", "city": "大阪市浪速区", "flood_risk_level": 2, "landslide_risk_level": 0},
    # 京都府
    {"prefecture": "京都府", "city": "京都市中京区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "京都府", "city": "京都市左京区", "flood_risk_level": 1, "landslide_risk_level": 2},
    # 愛知県
    {"prefecture": "愛知県", "city": "名古屋市中区", "flood_risk_level": 1, "landslide_risk_level": 0},
    {"prefecture": "愛知県", "city": "名古屋市西区", "flood_risk_level": 3, "landslide_risk_level": 0},
    # 福岡県
    {"prefecture": "福岡県", "city": "福岡市博多区", "flood_risk_level": 2, "landslide_risk_level": 0},
    {"prefecture": "福岡県", "city": "福岡市中央区", "flood_risk_level": 1, "landslide_risk_level": 0},
]


def import_hazard_map(csv_path=None):
    """
    ハザードマップ（浸水・土砂リスク）データの同期・洗い替え
    """
    logger.info("Syncing HazardMapPotential records...")
    count = 0

    if csv_path and os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pref = row.get("prefecture", "").strip()
                city = row.get("city", "").strip()
                if not pref or not city:
                    continue
                flood = int(row.get("flood_risk_level", 0))
                landslide = int(row.get("landslide_risk_level", 0))
                HazardMapPotential.objects.update_or_create(
                    prefecture=pref,
                    city=city,
                    defaults={
                        "flood_risk_level": flood,
                        "landslide_risk_level": landslide
                    }
                )
                count += 1
    else:
        # デフォルトマスタデータの適用
        for item in DEFAULT_HAZARD_DATA:
            HazardMapPotential.objects.update_or_create(
                prefecture=item["prefecture"],
                city=item["city"],
                defaults={
                    "flood_risk_level": item["flood_risk_level"],
                    "landslide_risk_level": item["landslide_risk_level"]
                }
            )
            count += 1

    logger.info(f"HazardMapPotential sync completed: {count} records updated/created.")
    return count


def import_urban_planning_zones(csv_path=None):
    """
    用途地域規制マスタの同期・洗い替え
    """
    logger.info("Syncing UrbanPlanningZonePotential records...")
    count = 0

    if csv_path and os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                z_name = row.get("zone_name", "").strip()
                if not z_name:
                    continue
                kenpei = int(row.get("max_kenpei", 60))
                youseki = int(row.get("max_youseki", 200))
                UrbanPlanningZonePotential.objects.update_or_create(
                    zone_name=z_name,
                    defaults={
                        "max_kenpei": kenpei,
                        "max_youseki": youseki
                    }
                )
                count += 1
    else:
        # デフォルト用途地域マスタの適用
        for item in DEFAULT_URBAN_ZONES:
            UrbanPlanningZonePotential.objects.update_or_create(
                zone_name=item["zone_name"],
                defaults={
                    "max_kenpei": item["max_kenpei"],
                    "max_youseki": item["max_youseki"]
                }
            )
            count += 1

    logger.info(f"UrbanPlanningZonePotential sync completed: {count} records updated/created.")
    return count
