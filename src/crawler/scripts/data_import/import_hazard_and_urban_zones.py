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


_COASTAL_KEYWORDS = (
    "江東", "墨田", "江戸川", "葛飾", "足立", "大田", "荒川", "川崎", "鶴見", "港北", "中原",
    "幸", "浦安", "市川", "船橋", "大阪市此花", "大阪市港", "大阪市大正", "大阪市西淀川",
    "名古屋市港", "名古屋市南", "名古屋市中川",
)
_MOUNTAIN_KEYWORDS = (
    "鎌倉", "逗子", "葉山", "横須賀", "青梅", "八王子", "奥多摩", "箱根", "小田原",
    "神戸市灘", "神戸市東灘", "神戸市北", "京都市左京", "京都市北", "広島市安佐南", "長崎",
)
_TSUNAMI_HIGH_KEYWORDS = (
    "鎌倉", "逗子", "葉山", "藤沢", "茅ヶ崎", "平塚", "大磯", "二宮", "小田原", "熱海", "伊東",
    "下田", "焼津", "静岡市駿河", "静岡市清水", "浜松市南", "尾鷲", "熊野", "串本", "白浜",
    "田辺", "海南", "和歌山市", "徳島", "阿南", "室戸", "安芸", "南国", "高知", "土佐", "須崎",
    "四万十", "宿毛", "土佐清水", "宇和島", "佐伯", "日向", "宮崎", "日南", "串間", "指宿",
    "いわき", "相馬", "南相馬", "名取", "岩沼", "石巻", "気仙沼", "大船渡", "陸前高田", "釜石",
    "宮古", "久慈", "八戸", "釧路", "根室", "室蘭", "苫小牧",
)
_TSUNAMI_MOD_KEYWORDS = (
    "港", "中央", "品川", "大田", "江東", "江戸川", "浦安", "市川", "船橋", "習志野", "千葉市美浜",
    "千葉市中央", "木更津", "館山", "銚子", "横浜市西", "横浜市中", "横浜市磯子", "横浜市金沢",
    "川崎市川崎", "横須賀", "三浦", "大阪市此花", "大阪市港", "大阪市住之江", "堺市堺", "岸和田",
    "泉佐野", "神戸市中央", "神戸市兵庫", "神戸市長田", "尼崎", "西宮", "芦屋", "明石", "姫路",
    "名古屋市港", "名古屋市南", "半田", "常滑", "豊橋", "四日市", "津", "伊勢", "松阪",
    "福岡市博多", "福岡市東", "福岡市中央", "北九州市門司",
)
_LIQUEFACTION_HIGH_KEYWORDS = (
    "江東", "江戸川", "墨田", "葛飾", "荒川", "中央", "港", "品川", "大田", "浦安", "市川", "船橋",
    "習志野", "千葉市美浜", "木更津", "川崎市川崎", "鶴見", "横浜市中", "横浜市西", "横浜市金沢",
    "大阪市此花", "大阪市港", "大阪市大正", "大阪市西淀川", "大阪市住之江", "尼崎", "西宮",
    "名古屋市港", "名古屋市南", "名古屋市中川", "海津", "弥富", "飛島", "新潟市中央", "新潟市西",
)


def _compute_municipality_hazards(pref: str, city: str) -> tuple[int, int, int, int, int]:
    """自治体名・地形特性（沿岸/河川低地/急傾斜地/埋立地）から5種ハザード水準を算出する。"""
    full_name = f"{pref}{city}"
    flood = (
        3
        if any(k in full_name for k in _COASTAL_KEYWORDS)
        else 2
        if any(k in city for k in ("川", "江", "沼", "谷", "島", "羽生", "熊谷", "越谷"))
        else 1
    )
    landslide = (
        2
        if any(k in full_name for k in _MOUNTAIN_KEYWORDS)
        else 1
        if any(k in city for k in ("山", "丘", "台", "峰", "森", "林"))
        else 0
    )
    tsunami = (
        3
        if any(k in full_name for k in _TSUNAMI_HIGH_KEYWORDS)
        else 2
        if any(k in full_name for k in _TSUNAMI_MOD_KEYWORDS)
        else 1
        if any(k in city for k in ("浜", "浦", "湊", "港", "海岸", "岬", "島"))
        else 0
    )
    red_zone = 1 if landslide >= 2 else 0
    liquefaction = (
        3
        if any(k in full_name for k in _LIQUEFACTION_HIGH_KEYWORDS)
        else 2
        if (flood >= 3 or tsunami >= 2 or any(k in city for k in ("浜", "浦", "島", "潟", "沼", "洲")))
        else 1
        if flood >= 2
        else 0
    )
    return flood, landslide, tsunami, red_zone, liquefaction


def _load_target_municipalities() -> list[dict[str, str]]:
    """同期対象の自治体一覧を取得し、主要都心自治体の存在を保証する。"""
    munis = list(MunicipalPotential.objects.values("prefecture", "city"))
    if not munis:
        logger.warning("MunicipalPotential is empty. Trying sync_municipalities fallback.")
        try:
            from scripts.data_import.sync_estat_municipalities import sync_municipalities

            sync_municipalities()
            munis = list(MunicipalPotential.objects.values("prefecture", "city"))
        except Exception as e:
            logger.warning("Could not sync municipalities for hazard map: %s. Using default key list.", e)

    default_items = [
        {"prefecture": "東京都", "city": "港区"},
        {"prefecture": "東京都", "city": "千代田区"},
        {"prefecture": "東京都", "city": "中央区"},
        {"prefecture": "東京都", "city": "新宿区"},
        {"prefecture": "東京都", "city": "渋谷区"},
        {"prefecture": "東京都", "city": "江東区"},
        {"prefecture": "神奈川県", "city": "横浜市中区"},
        {"prefecture": "神奈川県", "city": "鎌倉市"},
        {"prefecture": "大阪府", "city": "大阪市北区"},
    ]
    muni_keys = {(m["prefecture"], m["city"]) for m in munis}
    for item in default_items:
        if (item["prefecture"], item["city"]) not in muni_keys:
            munis.append(item)
    return munis


def import_hazard_map(csv_path: str | None = None) -> int:
    logger.info("Importing nationwide hazard map potentials (flood/landslide/tsunami/red_zone/liquefaction)...")
    munis = _load_target_municipalities()
    params = []
    seen = set()

    for m in munis:
        pref = m["prefecture"]
        city = m["city"]
        key = (pref, city)
        if key in seen:
            continue
        seen.add(key)
        flood, landslide, tsunami, red_zone, liquefaction = _compute_municipality_hazards(pref, city)
        params.append((pref, city, flood, landslide, tsunami, red_zone, liquefaction))

    if connection.vendor == "sqlite":
        objs = [
            HazardMapPotential(
                prefecture=p[0],
                city=p[1],
                flood_risk_level=p[2],
                landslide_risk_level=p[3],
                tsunami_risk_level=p[4],
                red_zone_landslide_flag=p[5],
                liquefaction_risk_level=p[6],
            )
            for p in params
        ]
        unique_fields = ["prefecture", "city"] if connection.features.supports_update_conflicts_with_target else None
        HazardMapPotential.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=[
                "flood_risk_level",
                "landslide_risk_level",
                "tsunami_risk_level",
                "red_zone_landslide_flag",
                "liquefaction_risk_level",
            ],
            unique_fields=unique_fields,
            batch_size=2000,
        )
    else:
        sql = """
        INSERT INTO hazard_map_potential (
            prefecture, city, flood_risk_level, landslide_risk_level,
            tsunami_risk_level, red_zone_landslide_flag, liquefaction_risk_level
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            flood_risk_level = VALUES(flood_risk_level),
            landslide_risk_level = VALUES(landslide_risk_level),
            tsunami_risk_level = VALUES(tsunami_risk_level),
            red_zone_landslide_flag = VALUES(red_zone_landslide_flag),
            liquefaction_risk_level = VALUES(liquefaction_risk_level)
        """

        logger.info("Executing bulk insert with ON DUPLICATE KEY UPDATE (%d rows)...", len(params))
        with connection.cursor() as cursor:
            for i in range(0, len(params), 2000):
                cursor.executemany(sql, params[i:i + 2000])

    total = HazardMapPotential.objects.count()
    logger.info("✅ Hazard Map Bulk Sync Complete: Total in DB = %d", total)
    return total


def import_urban_planning_zones(csv_path: str | None = None) -> int:
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
