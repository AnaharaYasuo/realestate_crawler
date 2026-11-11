# -*- coding: utf-8 -*-
"""
国土交通省 地価公示（L01）・都道府県地価調査（L02）全国高速バルクインポート・同期モジュール
(scripts/data_import/import_mlit_land_prices.py)

国土交通省「国土数値情報 地価公示データ（L01）」および「都道府県地価調査データ（L02）」の
公式GeoJSONデータを自動ダウンロード・パースし、以下の2階層マスタへ高速バルク同期します:
1. 市区町村別マスタ (`land_price_potential`): 住宅地・商業地の平均地価・想定路線価・固定資産税評価額・変動率
2. 地点座標・町丁目別ミクロ地価マスタ (`land_price_point_potential`): 約4.7万地点の緯度経度・町丁目・前面道路・インフラ有無 (Issue #1360)
"""
import io
import json
import logging
import os
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from decimal import Decimal
from typing import Any

import requests
from django.db import connection

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env

setup_env.init_environment()

import realestateSettings

realestateSettings.configure()

from package.models.evaluation import LandPricePointPotential, LandPricePotential

logger = logging.getLogger(__name__)

MLIT_LAND_PRICE_ZIP_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-23/L01-23_GML.zip"
MLIT_PREF_LAND_SURVEY_ZIP_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-23/L02-23_GML.zip"

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

_KANJI_DIGIT_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_KANJI_CHOME_RE = re.compile(r"([一二三四五六七八九十]{1,4})丁目")
_CHOME_KEY_RE = re.compile(r"^([^\d\-]+?)(\d+)?(?:丁目|-|番)")
_LEADING_DIGIT_TAIL_RE = re.compile(r"\d.*$", re.DOTALL)


def _kanji_numeral_to_int(kanji_str: str) -> int | None:
    if not kanji_str:
        return None
    total = 0
    current = 0
    for ch in kanji_str:
        if ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch in _KANJI_DIGIT_MAP:
            current = _KANJI_DIGIT_MAP[ch]
        else:
            return None
    return total + current


def _replace_kanji_chome(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        val = _kanji_numeral_to_int(match.group(1))
        return f"{val}丁目" if val is not None else match.group(0)

    return _KANJI_CHOME_RE.sub(_repl, text)


def split_prefecture_and_city(address: str) -> tuple[str | None, str | None]:
    clean_addr = unicodedata.normalize("NFKC", address or "").replace("　", " ").strip()
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


def normalize_chome_key(pref: str, city: str, full_address: str) -> str:
    """都道府県・市区町村・フル住所から `parsers._extract_chome` 互換の正規化町丁目キーを生成する。"""
    addr = _replace_kanji_chome(unicodedata.normalize("NFKC", full_address or ""))
    rest = addr
    for prefix in (pref, city):
        p = unicodedata.normalize("NFKC", prefix or "")
        if p and p in rest:
            rest = rest.split(p, 1)[1]
    rest = "".join(rest.split()).removeprefix("大字")
    if not rest:
        return f"{pref}{city}"
    m = _CHOME_KEY_RE.match(rest)
    if m:
        town = m.group(1).strip()
        num = m.group(2) or ""
        return f"{pref}{city}{town}{num}"
    town_only = _LEADING_DIGIT_TAIL_RE.sub("", rest).strip()
    return f"{pref}{city}{town_only}"


def _extract_lon_lat(geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not geometry:
        return None, None
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return None, None
    try:
        if gtype == "Point" and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
        elif gtype == "MultiPoint" and coords and len(coords[0]) >= 2:
            lon, lat = float(coords[0][0]), float(coords[0][1])
        elif gtype == "Polygon" and coords and coords[0]:
            ring = coords[0]
            lon = sum(float(pt[0]) for pt in ring) / len(ring)
            lat = sum(float(pt[1]) for pt in ring) / len(ring)
        else:
            return None, None
    except (TypeError, ValueError, IndexError):
        return None, None

    if 20.0 <= lat <= 46.5 and 122.0 <= lon <= 154.5:
        return lon, lat
    return None, None


def _parse_infra_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return True
    s = str(val).strip().lower()
    return s not in ("0", "2", "false", "無", "なし")


def _parse_road_width_meters(raw_val: Any) -> float | None:
    if raw_val is None or raw_val == "":
        return None
    try:
        v = float(raw_val)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    # 国土数値情報 L01_037/L02_035 は 0.1m 単位整数（例: 60 -> 6.0m）で格納されるケースが多い
    return round(v / 10.0, 2) if v >= 25.0 else round(v, 2)


def _parse_optional_int(raw_val: Any) -> int | None:
    if raw_val is None or raw_val == "":
        return None
    try:
        v = int(float(raw_val))
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _parse_optional_decimal(raw_val: Any) -> Decimal | None:
    if raw_val is None or raw_val == "":
        return None
    try:
        return Decimal(str(round(float(raw_val), 2)))
    except (TypeError, ValueError):
        return None


def _resolve_survey_fields(props: dict[str, Any], default_survey: str) -> dict[str, Any]:
    is_l02 = "L02_006" in props or "L02_022" in props or default_survey == "L02"
    if is_l02 and "L01_006" not in props:
        return {
            "survey": "L02",
            "raw_code": str(props.get("L02_001") or props.get("L02_002") or ""),
            "price": props.get("L02_006"),
            "growth": props.get("L02_007"),
            "addr": str(props.get("L02_022") or props.get("L02_021") or ""),
            "use_code": str(props.get("L02_025") or props.get("L02_026") or ""),
            "road_width": _parse_road_width_meters(props.get("L02_035")),
            "has_gas": _parse_infra_bool(props.get("L02_042")),
            "has_water": _parse_infra_bool(props.get("L02_043")),
            "has_sewer": _parse_infra_bool(props.get("L02_044")),
            "station_name": str(props.get("L02_045") or "").replace("駅", "").strip(),
            "station_distance_m": _parse_optional_int(props.get("L02_046")),
            "zone_name": str(props.get("L02_049") or "").strip(),
        }
    return {
        "survey": "L01",
        "raw_code": str(props.get("L01_001") or props.get("L01_002") or ""),
        "price": props.get("L01_006"),
        "growth": props.get("L01_007"),
        "addr": str(props.get("L01_024") or props.get("L01_023") or ""),
        "use_code": str(props.get("L01_027") or props.get("L01_028") or ""),
        "road_width": _parse_road_width_meters(props.get("L01_037")),
        "has_gas": _parse_infra_bool(props.get("L01_044")),
        "has_water": _parse_infra_bool(props.get("L01_045")),
        "has_sewer": _parse_infra_bool(props.get("L01_046")),
        "station_name": str(props.get("L01_047") or "").replace("駅", "").strip(),
        "station_distance_m": _parse_optional_int(props.get("L01_048")),
        "zone_name": str(props.get("L01_051") or "").strip(),
    }


def extract_point_records_from_geojson_features(
    features: list[dict[str, Any]],
    default_survey: str = "L01",
) -> list[dict[str, Any]]:
    """L01(地価公示)・L02(都道府県地価調査) GeoJSON Feature配列から地点別ミクロ地価レコードを抽出する。"""
    point_records: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for idx, feat in enumerate(features):
        props = feat.get("properties") or {}
        lon, lat = _extract_lon_lat(feat.get("geometry"))
        if lon is None or lat is None:
            continue

        parsed = _resolve_survey_fields(props, default_survey=default_survey)
        raw_price = parsed["price"]
        try:
            land_price = int(float(raw_price))
        except (TypeError, ValueError):
            continue
        if land_price <= 0:
            continue

        pref, city = split_prefecture_and_city(parsed["addr"])
        if not pref or not city:
            continue

        land_use = "residential" if "住" in parsed["use_code"] else "commercial"
        chome_key = normalize_chome_key(pref, city, parsed["addr"])
        survey = parsed["survey"]
        base_code = parsed["raw_code"] or str(idx)
        point_code = f"{survey}:{pref}:{city}:{base_code}:{lat:.5f}:{lon:.5f}"[:100]
        if point_code in seen_codes:
            continue
        seen_codes.add(point_code)

        point_records.append({
            "point_code": point_code,
            "survey_type": survey,
            "prefecture": pref,
            "city": city,
            "chome_key": chome_key[:150],
            "latitude": lat,
            "longitude": lon,
            "land_price": land_price,
            "growth_rate": _parse_optional_decimal(parsed["growth"]),
            "land_use": land_use,
            "zone_name": parsed["zone_name"][:100],
            "road_width": parsed["road_width"],
            "station_name": parsed["station_name"][:100],
            "station_distance_m": parsed["station_distance_m"],
            "has_gas": parsed["has_gas"],
            "has_water": parsed["has_water"],
            "has_sewer": parsed["has_sewer"],
        })

    return point_records


def _read_geojson_features_from_zip(zip_bytes: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        geojson_names = [n for n in z.namelist() if n.lower().endswith(".geojson")]
        if not geojson_names:
            raise FileNotFoundError("GeoJSON file not found in downloaded MLIT archive.")
        # 全国統合ファイル（L01-23.geojson / L02-23.geojson 等）を優先
        geojson_names.sort(key=lambda n: (0 if ("L01-" in n or "L02-" in n) else 1, len(n)))
        target = geojson_names[0]
        logger.info("Reading GeoJSON: %s...", target)
        data = json.loads(z.read(target).decode("utf-8"))
        return data.get("features", [])


def _aggregate_municipal_records(point_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    city_stats: dict[tuple[str, str], dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for pt in point_records:
        growth_f = float(pt["growth_rate"]) if pt["growth_rate"] is not None else 0.0
        city_stats[(pt["prefecture"], pt["city"])][pt["land_use"]].append((float(pt["land_price"]), growth_f))

    records: list[dict[str, Any]] = []
    for (pref, city), uses in city_stats.items():
        for land_use in ("residential", "commercial"):
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
    return records


def download_survey_points(url: str, survey_type: str = "L01", timeout: int = 120) -> list[dict[str, Any]]:
    logger.info("Downloading MLIT %s Land Price data from %s...", survey_type, url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    features = _read_geojson_features_from_zip(resp.content)
    pts = extract_point_records_from_geojson_features(features, default_survey=survey_type)
    logger.info("Extracted %d valid %s survey points (from %d raw features).", len(pts), survey_type, len(features))
    return pts


def download_and_extract_land_prices(url: str = MLIT_LAND_PRICE_ZIP_URL, timeout: int = 120) -> list[dict[str, Any]]:
    pts = download_survey_points(url=url, survey_type="L01", timeout=timeout)
    records = _aggregate_municipal_records(pts)
    logger.info("Aggregated into %d municipal land price records across Japan.", len(records))
    return records


def upsert_municipal_land_prices(records: list[dict[str, Any]]) -> None:
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
            r["estimated_rosenka_price"], r["estimated_fixed_asset_price"], r["land_price_growth_rate"],
        )
        for r in records
    ]
    if connection.vendor == "sqlite":
        objs = [
            LandPricePotential(
                prefecture=p[0], city=p[1], land_use=p[2], average_land_price=p[3],
                estimated_rosenka_price=p[4], estimated_fixed_asset_price=p[5], land_price_growth_rate=p[6],
            )
            for p in params
        ]
        LandPricePotential.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=[
                "average_land_price", "estimated_rosenka_price",
                "estimated_fixed_asset_price", "land_price_growth_rate",
            ],
            unique_fields=["prefecture", "city", "land_use"],
            batch_size=2000,
        )
        return

    chunk_size = 2000
    with connection.cursor() as cursor:
        for i in range(0, len(params), chunk_size):
            cursor.executemany(sql, params[i:i + chunk_size])


def upsert_land_price_points(point_records: list[dict[str, Any]]) -> int:
    """地点別地価マスタ (`land_price_point_potential`) を一括高速同期する。"""
    if not point_records:
        return 0

    if connection.vendor == "sqlite":
        objs = [LandPricePointPotential(**pt) for pt in point_records]
        LandPricePointPotential.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=[
                "survey_type", "prefecture", "city", "chome_key",
                "latitude", "longitude", "land_price", "growth_rate",
                "land_use", "zone_name", "road_width", "station_name",
                "station_distance_m", "has_gas", "has_water", "has_sewer",
            ],
            unique_fields=["point_code"],
            batch_size=2000,
        )
        return LandPricePointPotential.objects.count()

    sql = """
    INSERT INTO land_price_point_potential (
        point_code, survey_type, prefecture, city, chome_key,
        latitude, longitude, land_price, growth_rate, land_use,
        zone_name, road_width, station_name, station_distance_m,
        has_gas, has_water, has_sewer, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        survey_type = VALUES(survey_type),
        prefecture = VALUES(prefecture),
        city = VALUES(city),
        chome_key = VALUES(chome_key),
        latitude = VALUES(latitude),
        longitude = VALUES(longitude),
        land_price = VALUES(land_price),
        growth_rate = VALUES(growth_rate),
        land_use = VALUES(land_use),
        zone_name = VALUES(zone_name),
        road_width = VALUES(road_width),
        station_name = VALUES(station_name),
        station_distance_m = VALUES(station_distance_m),
        has_gas = VALUES(has_gas),
        has_water = VALUES(has_water),
        has_sewer = VALUES(has_sewer),
        updated_at = NOW()
    """
    params = [
        (
            pt["point_code"], pt["survey_type"], pt["prefecture"], pt["city"], pt["chome_key"],
            pt["latitude"], pt["longitude"], pt["land_price"], pt["growth_rate"], pt["land_use"],
            pt["zone_name"], pt["road_width"], pt["station_name"], pt["station_distance_m"],
            int(bool(pt["has_gas"])), int(bool(pt["has_water"])), int(bool(pt["has_sewer"])),
        )
        for pt in point_records
    ]
    chunk_size = 2000
    with connection.cursor() as cursor:
        for i in range(0, len(params), chunk_size):
            cursor.executemany(sql, params[i:i + chunk_size])
    return LandPricePointPotential.objects.count()


def import_land_prices(csv_path: str | None = None, include_l02: bool = True) -> int:
    _ = csv_path
    logger.info("Starting synchronization of nationwide MLIT land prices (L01 + L02)...")
    all_points = download_survey_points(MLIT_LAND_PRICE_ZIP_URL, survey_type="L01")
    if include_l02:
        try:
            l02_points = download_survey_points(MLIT_PREF_LAND_SURVEY_ZIP_URL, survey_type="L02")
            all_points.extend(l02_points)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MLIT L02 download failed (continuing with L01 points): %s", exc)

    if not all_points:
        raise RuntimeError("No land price records extracted from MLIT data source.")

    muni_records = _aggregate_municipal_records(all_points)
    upsert_municipal_land_prices(muni_records)
    total_points = upsert_land_price_points(all_points)

    total_muni = LandPricePotential.objects.count()
    logger.info(
        "✅ MLIT Land prices sync complete: Municipal rows = %d, Spatial points = %d",
        total_muni,
        total_points,
    )
    return total_muni


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import_land_prices()
