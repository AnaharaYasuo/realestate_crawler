# -*- coding: utf-8 -*-
"""
国土交通省 地価公示（L01）全国全自治体（約26,000地点）高速バルクインポート・同期モジュール
(scripts/data_import/import_mlit_land_prices.py)

国土交通省「国土数値情報 地価公示データ（L01）」の公式GeoJSONデータを自動ダウンロード・パースし、
全国1,741市区町村別の住宅地（residential）・商業地（commercial）の平均公示地価、
想定路線価、想定固定資産税評価額、地価変動率を算出してDB（land_price_potential）に
ON DUPLICATE KEY UPDATE による高速バルクSQLで一括同期・洗い替えします。
"""
import io
import json
import logging
import os
import re
import sys
import zipfile
from collections import defaultdict
from decimal import Decimal
import requests
from django.db import connection

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import LandPricePotential

logger = logging.getLogger(__name__)

MLIT_LAND_PRICE_ZIP_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-23/L01-23_GML.zip"

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
]


def split_prefecture_and_city(address: str) -> tuple[str | None, str | None]:
    clean_addr = address.replace("　", " ").strip()
    matched_pref = None
    rest = clean_addr
    for p in PREFECTURES:
        if clean_addr.startswith(p):
            matched_pref = p
            rest = clean_addr[len(p):].strip()
            break
            
    if not matched_pref:
        return None, None

    m_ward = re.match(r"^([^市区町村]+市[^市区町村]+区)", rest)
    if m_ward:
        return matched_pref, m_ward.group(1)

    m_city = re.match(r"^([^市区町村]+(?:市|区|町|村))", rest)
    if m_city:
        return matched_pref, m_city.group(1)

    return matched_pref, rest


def download_and_extract_land_prices(url: str = MLIT_LAND_PRICE_ZIP_URL, timeout: int = 120) -> list[dict]:
    logger.info("Downloading MLIT Land Price data from %s...", url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    logger.info("Downloaded %d bytes. Parsing GeoJSON...", len(resp.content))

    city_stats = defaultdict(lambda: defaultdict(list))

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        geojson_name = None
        for name in z.namelist():
            if name.endswith("L01-23.geojson"):
                geojson_name = name
                break

        if not geojson_name:
            raise FileNotFoundError("L01-23.geojson not found in downloaded MLIT archive.")

        logger.info("Reading GeoJSON: %s...", geojson_name)
        content = z.read(geojson_name)
        data = json.loads(content.decode("utf-8"))
        features = data.get("features", [])
        logger.info("Total land price survey points: %d", len(features))

        for f in features:
            props = f.get("properties", {})
            addr = props.get("L01_024") or ""
            price = props.get("L01_006")
            growth = props.get("L01_007") or 0.0
            use_code = props.get("L01_027") or ""

            pref, city = split_prefecture_and_city(addr)
            if not pref or not city or not price or price <= 0:
                continue

            use = "residential" if "住" in use_code else "commercial"
            city_stats[(pref, city)][use].append((float(price), float(growth)))

    records = []
    for (pref, city), uses in city_stats.items():
        for land_use in ["residential", "commercial"]:
            points = uses.get(land_use, [])
            if not points:
                continue
            avg_price = int(sum(p[0] for p in points) / len(points))
            avg_growth = Decimal(str(round(sum(p[1] for p in points) / len(points), 2)))
            records.append({
                "prefecture": pref,
                "city": city,
                "land_use": land_use,
                "average_land_price": avg_price,
                "estimated_rosenka_price": int(avg_price * 0.8),
                "estimated_fixed_asset_price": int(avg_price * 0.7),
                "land_price_growth_rate": avg_growth,
            })

    logger.info("Aggregated into %d municipal land price records across Japan.", len(records))
    return records


def import_land_prices(csv_path: str = None) -> int:
    logger.info("Starting synchronization of nationwide MLIT land prices...")
    records = download_and_extract_land_prices()
    if not records:
        raise RuntimeError("No land price records extracted from MLIT data source.")

    sql = """
    INSERT INTO land_price_potential (
        prefecture, city, land_use, average_land_price,
        estimated_rosenka_price, estimated_fixed_asset_price, land_price_growth_rate
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        average_land_price = VALUES(average_land_price),
        estimated_rosenka_price = VALUES(estimated_rosenka_price),
        estimated_fixed_asset_price = VALUES(estimated_fixed_asset_price),
        land_price_growth_rate = VALUES(land_price_growth_rate)
    """

    params = [
        (
            r["prefecture"], r["city"], r["land_use"], r["average_land_price"],
            r["estimated_rosenka_price"], r["estimated_fixed_asset_price"], r["land_price_growth_rate"]
        )
        for r in records
    ]

    if connection.vendor == "sqlite":
        objs = [
            LandPricePotential(
                prefecture=p[0],
                city=p[1],
                land_use=p[2],
                average_land_price=p[3],
                estimated_rosenka_price=p[4],
                estimated_fixed_asset_price=p[5],
                land_price_growth_rate=p[6],
            )
            for p in params
        ]
        LandPricePotential.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=[
                "average_land_price",
                "estimated_rosenka_price",
                "estimated_fixed_asset_price",
                "land_price_growth_rate",
            ],
            unique_fields=["prefecture", "city", "land_use"],
            batch_size=2000,
        )
    else:
        logger.info("Executing bulk insert with ON DUPLICATE KEY UPDATE (%d rows)...", len(params))
        chunk_size = 2000
        with connection.cursor() as cursor:
            for i in range(0, len(params), chunk_size):
                chunk = params[i:i + chunk_size]
                cursor.executemany(sql, chunk)

    total = LandPricePotential.objects.count()
    logger.info("✅ MLIT Land prices bulk sync complete: Total in DB = %d", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import_land_prices()
