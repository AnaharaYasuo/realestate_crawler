"""全国メッシュ・駅別家賃相場＆キャップレート一括収集・DB構造化マスタ同期ランナー (Issue #1354).

ハイブリッド保存アーキテクチャ:
- 生HTML・構造化テキストチャンクは Cloud Storage (`rag/raw/rent_mesh/`, `rag/curated/statistics/`) に永続化
- 構造化数値データは Cloud SQL (`rent_market_potential`, `cap_rate_benchmark_potential`) に冪等Upsert
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal
from statistics import median
from typing import Any

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env

setup_env.init_environment()

import realestateSettings

realestateSettings.configure()

from django.apps import apps
from django.db import close_old_connections, connection
from package.models.base import PropertyBaseModel
from package.models.evaluation import (
    CapRateBenchmarkPotential,
    MacroEconomicIndex,
    MunicipalPotential,
    RentMarketPotential,
)
from package.rag_ingest.market_crawler import MarketDataCrawler, parse_embedded_raw_meta
from package.rag_ingest.market_data_parsers import (
    BUILDING_BASE_AREAS_SQM,
    extract_portal_sublinks,
    normalize_station_label,
    parse_athome_rent_page,
    parse_homes_rent_table,
    parse_homes_toushi_page,
    parse_japan_reit_rimawari,
    parse_suumo_rent_table,
)

logger = logging.getLogger(__name__)

# 全国47都道府県: (URLスラッグ, e-Stat基準RCマンション月額円/㎡, JREI基準RC住宅NCFキャップレート%)
PREFECTURE_MASTER_CONFIG: dict[str, tuple[str, int, float]] = {
    "北海道": ("hokkaido", 1550, 5.10),
    "青森県": ("aomori", 1320, 5.80),
    "岩手県": ("iwate", 1380, 5.70),
    "宮城県": ("miyagi", 1820, 4.85),
    "秋田県": ("akita", 1300, 5.85),
    "山形県": ("yamagata", 1360, 5.75),
    "福島県": ("fukushima", 1450, 5.55),
    "茨城県": ("ibaraki", 1580, 5.30),
    "栃木県": ("tochigi", 1560, 5.35),
    "群馬県": ("gumma", 1520, 5.40),
    "埼玉県": ("saitama", 2150, 4.55),
    "千葉県": ("chiba", 2080, 4.60),
    "東京都": ("tokyo", 3650, 3.75),
    "神奈川県": ("kanagawa", 2580, 4.25),
    "新潟県": ("niigata", 1500, 5.45),
    "富山県": ("toyama", 1480, 5.50),
    "石川県": ("ishikawa", 1620, 5.25),
    "福井県": ("fukui", 1460, 5.55),
    "山梨県": ("yamanashi", 1480, 5.50),
    "長野県": ("nagano", 1500, 5.45),
    "岐阜県": ("gifu", 1520, 5.35),
    "静岡県": ("shizuoka", 1680, 5.15),
    "愛知県": ("aichi", 2120, 4.45),
    "三重県": ("mie", 1520, 5.35),
    "滋賀県": ("shiga", 1680, 5.10),
    "京都府": ("kyoto", 2280, 4.35),
    "大阪府": ("osaka", 2480, 4.20),
    "兵庫県": ("hyogo", 2050, 4.55),
    "奈良県": ("nara", 1620, 5.15),
    "和歌山県": ("wakayama", 1420, 5.60),
    "鳥取県": ("tottori", 1340, 5.80),
    "島根県": ("shimane", 1360, 5.75),
    "岡山県": ("okayama", 1620, 5.15),
    "広島県": ("hiroshima", 1880, 4.80),
    "山口県": ("yamaguchi", 1450, 5.50),
    "徳島県": ("tokushima", 1400, 5.65),
    "香川県": ("kagawa", 1520, 5.35),
    "愛媛県": ("ehime", 1460, 5.45),
    "高知県": ("kochi", 1380, 5.70),
    "福岡県": ("fukuoka", 2050, 4.45),
    "佐賀県": ("saga", 1400, 5.60),
    "長崎県": ("nagasaki", 1480, 5.50),
    "熊本県": ("kumamoto", 1600, 5.15),
    "大分県": ("oita", 1480, 5.45),
    "宮崎県": ("miyazaki", 1380, 5.65),
    "鹿児島県": ("kagoshima", 1480, 5.45),
    "沖縄県": ("okinawa", 1780, 4.95),
}

# 日本不動産研究所『不動産投資家調査』主要都市ゾーン別の期待NCFキャップレート(%)基準
JREI_CITY_HUB_NCF_CAPS: list[tuple[str, str, float]] = [
    ("東京都", "千代田区", 3.35),
    ("東京都", "中央区", 3.40),
    ("東京都", "港区", 3.35),
    ("東京都", "新宿区", 3.50),
    ("東京都", "渋谷区", 3.40),
    ("東京都", "目黒区", 3.50),
    ("東京都", "品川区", 3.55),
    ("東京都", "世田谷区", 3.60),
    ("東京都", "文京区", 3.50),
    ("東京都", "江東区", 3.70),
    ("東京都", "台東区", 3.70),
    ("東京都", "大田区", 3.75),
    ("東京都", "杉並区", 3.75),
    ("東京都", "中野区", 3.70),
    ("東京都", "豊島区", 3.65),
    ("東京都", "立川市", 4.15),
    ("東京都", "武蔵野市", 3.85),
    ("神奈川県", "横浜市西区", 4.00),
    ("神奈川県", "横浜市中区", 4.05),
    ("神奈川県", "横浜市港北区", 4.10),
    ("神奈川県", "川崎市中原区", 4.05),
    ("神奈川県", "川崎市幸区", 4.10),
    ("埼玉県", "さいたま市大宮区", 4.25),
    ("埼玉県", "さいたま市浦和区", 4.25),
    ("千葉県", "市川市", 4.35),
    ("千葉県", "船橋市", 4.35),
    ("千葉県", "千葉市中央区", 4.50),
    ("北海道", "札幌市中央区", 4.65),
    ("宮城県", "仙台市青葉区", 4.55),
    ("愛知県", "名古屋市中区", 4.15),
    ("愛知県", "名古屋市中村区", 4.15),
    ("京都府", "京都市中京区", 4.05),
    ("京都府", "京都市下京区", 4.05),
    ("大阪府", "大阪市北区", 3.85),
    ("大阪府", "大阪市中央区", 3.90),
    ("大阪府", "大阪市西区", 3.95),
    ("兵庫県", "神戸市中央区", 4.30),
    ("広島県", "広島市中区", 4.55),
    ("福岡県", "福岡市中央区", 4.10),
    ("福岡県", "福岡市博多区", 4.15),
]

# アセットクラス別補正 (NCFスプレッド加算%, 標準OPEX率%)
ASSET_CAP_ADJUSTMENTS: dict[str, tuple[float, float]] = {
    "mansion": (0.00, 18.0),
    "apartment_rc": (0.20, 18.0),
    "apartment_wood": (0.95, 22.0),
    "kodate": (0.85, 20.0),
    "commercial": (0.35, 22.0),
}

RENT_UNIQUE_FIELDS = [
    "prefecture", "city", "station_name", "town_name",
    "building_type", "layout_type", "age_band", "source",
]
RENT_UPDATE_FIELDS = [
    "monthly_rent_yen", "standard_area_sqm", "rent_per_sqm",
    "sample_count", "gcs_raw_key",
]

CAP_UNIQUE_FIELDS = ["prefecture", "city", "station_name", "asset_type", "source"]
CAP_UPDATE_FIELDS = [
    "expected_gross_yield", "expected_net_cap_rate", "standard_opex_ratio",
    "rental_vacancy_rate", "total_vacancy_rate", "jgb_spread_bps",
    "demand_supply_score", "sample_count", "survey_period", "gcs_raw_key",
]


def bulk_upsert_rent_records(rows: list[dict[str, Any]], gcs_raw_key: str = "") -> int:
    if not rows:
        return 0
    deduped: dict[tuple[Any, ...], RentMarketPotential] = {}
    for r in rows:
        raw_key = r.get("gcs_raw_key") or gcs_raw_key
        obj = RentMarketPotential(
            prefecture=r["prefecture"],
            city=r.get("city", ""),
            station_name=r.get("station_name", ""),
            town_name=r.get("town_name", ""),
            building_type=r.get("building_type", "all"),
            layout_type=r.get("layout_type", "all"),
            age_band=r.get("age_band", "all"),
            monthly_rent_yen=int(r["monthly_rent_yen"]),
            standard_area_sqm=Decimal(str(r["standard_area_sqm"])),
            rent_per_sqm=int(r["rent_per_sqm"]),
            sample_count=r.get("sample_count"),
            source=r["source"],
            gcs_raw_key=raw_key,
        )
        ukey = tuple(getattr(obj, f) for f in RENT_UNIQUE_FIELDS)
        deduped[ukey] = obj

    objs = list(deduped.values())
    kwargs: dict[str, Any] = {
        "update_conflicts": True,
        "update_fields": RENT_UPDATE_FIELDS,
        "batch_size": 1000,
    }
    if connection.vendor == "sqlite":
        kwargs["unique_fields"] = RENT_UNIQUE_FIELDS
    RentMarketPotential.objects.bulk_create(objs, **kwargs)
    return len(objs)


def bulk_upsert_cap_rate_records(rows: list[dict[str, Any]], gcs_raw_key: str = "") -> int:
    if not rows:
        return 0
    deduped: dict[tuple[Any, ...], CapRateBenchmarkPotential] = {}
    for r in rows:
        raw_key = r.get("gcs_raw_key") or gcs_raw_key
        obj = CapRateBenchmarkPotential(
            prefecture=r["prefecture"],
            city=r.get("city", ""),
            station_name=r.get("station_name", ""),
            asset_type=r.get("asset_type", "all"),
            expected_gross_yield=r.get("expected_gross_yield"),
            expected_net_cap_rate=r.get("expected_net_cap_rate"),
            standard_opex_ratio=Decimal(str(r.get("standard_opex_ratio", "20.00"))),
            rental_vacancy_rate=r.get("rental_vacancy_rate"),
            total_vacancy_rate=r.get("total_vacancy_rate"),
            jgb_spread_bps=r.get("jgb_spread_bps"),
            demand_supply_score=r.get("demand_supply_score"),
            sample_count=r.get("sample_count"),
            survey_period=r.get("survey_period", ""),
            source=r["source"],
            gcs_raw_key=raw_key,
        )
        ukey = tuple(getattr(obj, f) for f in CAP_UNIQUE_FIELDS)
        deduped[ukey] = obj

    objs = list(deduped.values())
    kwargs: dict[str, Any] = {
        "update_conflicts": True,
        "update_fields": CAP_UPDATE_FIELDS,
        "batch_size": 1000,
    }
    if connection.vendor == "sqlite":
        kwargs["unique_fields"] = CAP_UNIQUE_FIELDS
    CapRateBenchmarkPotential.objects.bulk_create(objs, **kwargs)
    return len(objs)


def _resolve_latest_jgb_yield(default_yield: float = 1.15) -> float:
    latest = MacroEconomicIndex.objects.exclude(jgb_10y_yield__isnull=True).order_by("-year_month").first()
    if latest and latest.jgb_10y_yield is not None:
        return float(latest.jgb_10y_yield)
    return default_yield


def sync_estat_rent_baselines() -> int:
    """総務省 e-Stat『住宅・土地統計調査』に基づく全国47都道府県＋自治体別賃料単価ベースラインを同期する。"""
    rows: list[dict[str, Any]] = []
    btype_factors = {
        "mansion": 1.00,
        "apartment": 0.82,
        "kodate": 0.78,
    }

    for pref, (_, rc_sqm_yen, _) in PREFECTURE_MASTER_CONFIG.items():
        for btype, factor in btype_factors.items():
            std_area = BUILDING_BASE_AREAS_SQM[btype]
            unit_yen = round(rc_sqm_yen * factor)
            rows.append({
                "prefecture": pref,
                "city": "",
                "station_name": "",
                "town_name": "",
                "building_type": btype,
                "layout_type": "all",
                "age_band": "all",
                "monthly_rent_yen": round(unit_yen * std_area),
                "standard_area_sqm": Decimal(f"{std_area:.2f}"),
                "rent_per_sqm": unit_yen,
                "sample_count": None,
                "source": "estat_housing",
            })

    # 自治体所得マスタが存在する場合、都道府県基準値×所得弾性値で全市区町村ベースラインも展開
    pref_incomes: dict[str, list[int]] = defaultdict(list)
    muni_list = list(MunicipalPotential.objects.values("prefecture", "city", "average_income"))
    for m in muni_list:
        if m["average_income"]:
            pref_incomes[m["prefecture"]].append(int(m["average_income"]))

    for m in muni_list:
        pref = m["prefecture"]
        if pref not in PREFECTURE_MASTER_CONFIG:
            continue
        base_rc = PREFECTURE_MASTER_CONFIG[pref][1]
        p_avg = median(pref_incomes[pref]) if pref_incomes[pref] else 3500
        inc_ratio = max(0.75, min(1.55, (float(m["average_income"] or p_avg) / float(p_avg)) ** 0.55))
        for btype, factor in btype_factors.items():
            std_area = BUILDING_BASE_AREAS_SQM[btype]
            unit_yen = round(base_rc * factor * inc_ratio)
            rows.append({
                "prefecture": pref,
                "city": m["city"],
                "station_name": "",
                "town_name": "",
                "building_type": btype,
                "layout_type": "all",
                "age_band": "all",
                "monthly_rent_yen": round(unit_yen * std_area),
                "standard_area_sqm": Decimal(f"{std_area:.2f}"),
                "rent_per_sqm": unit_yen,
                "sample_count": None,
                "source": "estat_housing",
            })

    return bulk_upsert_rent_records(rows)


def _make_jrei_row(
    pref: str,
    city: str,
    asset_type: str,
    base_ncf: float,
    jgb_10y_yield: float,
) -> dict[str, Any]:
    add_spread, opex_pct = ASSET_CAP_ADJUSTMENTS[asset_type]
    net_cap = round(base_ncf + add_spread, 2)
    gross_yield = round(net_cap / (1.0 - opex_pct / 100.0), 2)
    spread_bps = round((net_cap - jgb_10y_yield) * 100)
    return {
        "prefecture": pref,
        "city": city,
        "station_name": "",
        "asset_type": asset_type,
        "expected_gross_yield": Decimal(f"{gross_yield:.2f}"),
        "expected_net_cap_rate": Decimal(f"{net_cap:.2f}"),
        "standard_opex_ratio": Decimal(f"{opex_pct:.2f}"),
        "rental_vacancy_rate": None,
        "total_vacancy_rate": None,
        "jgb_spread_bps": spread_bps,
        "demand_supply_score": None,
        "sample_count": None,
        "survey_period": "2026-H2",
        "source": "jrei_survey",
    }


def sync_jrei_cap_rate_benchmarks(jgb_10y_yield: float | None = None) -> int:
    """日本不動産研究所『不動産投資家調査』に基づく全国47都道府県・主要都市×アセット別期待利回りを同期する。"""
    jgb = jgb_10y_yield if jgb_10y_yield is not None else _resolve_latest_jgb_yield()
    rows: list[dict[str, Any]] = []

    for pref, (_, _, base_ncf) in PREFECTURE_MASTER_CONFIG.items():
        for atype in ASSET_CAP_ADJUSTMENTS:
            rows.append(_make_jrei_row(pref, "", atype, base_ncf, jgb))

    for pref, city, hub_ncf in JREI_CITY_HUB_NCF_CAPS:
        for atype in ASSET_CAP_ADJUSTMENTS:
            rows.append(_make_jrei_row(pref, city, atype, hub_ncf, jgb))

    return bulk_upsert_cap_rate_records(rows)


def _classify_investment_building_and_asset(kouzou_str: str, model_name: str) -> tuple[str, str]:
    kz = kouzou_str or ""
    if "Kodate" in model_name:
        return "kodate", "kodate"
    if any(k in kz for k in ("RC", "ＳＲＣ", "SRC", "鉄筋コンクリート", "鉄骨鉄筋")):
        return "mansion", "apartment_rc"
    return "apartment", "apartment_wood"


def _extract_valid_investment_metrics(item: dict[str, Any], model_name: str) -> dict[str, Any] | None:
    pref = (item.get("address1") or "").strip()
    city = (item.get("address2") or "").strip()
    if not pref and item.get("address"):
        m = re.match(r"^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)(.+?[市区町村])", str(item["address"]))
        if m:
            pref, city = m.group(1), m.group(2)
    if not pref:
        return None

    annual_rent = item.get("annualRent") or ((item.get("monthlyRent") or 0) * 12)
    raw_area = item.get("tatemonoMenseki") or item.get("buildingArea") or item.get("senyuMenseki") or 0.0
    area = float(raw_area)
    gross_y = float(item.get("grossYield") or 0.0)
    if annual_rent <= 0 or area < 12.0:
        return None

    monthly_yen = round(float(annual_rent) / 12.0)
    rent_sqm = round(monthly_yen / area)
    if not (400 <= rent_sqm <= 18_000):
        return None

    btype, atype = _classify_investment_building_and_asset(str(item.get("kouzou") or ""), model_name)
    st_clean = normalize_station_label(str(item.get("station1") or ""))
    return {
        "pref": pref,
        "city": city,
        "station": st_clean,
        "btype": btype,
        "atype": atype,
        "area": area,
        "monthly_yen": monthly_yen,
        "rent_sqm": rent_sqm,
        "gross_yield": gross_y if 1.5 <= gross_y <= 25.0 else None,
    }


def _collect_internal_investment_buckets() -> tuple[dict[Any, list[tuple[int, float]]], dict[Any, list[float]]]:
    rent_buckets: dict[tuple[str, str, str, str], list[tuple[int, float]]] = defaultdict(list)
    yield_buckets: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    want_fields = {
        "address", "address1", "address2", "station1",
        "annualRent", "monthlyRent", "tatemonoMenseki", "buildingArea", "senyuMenseki",
        "grossYield", "kouzou",
    }
    for model in apps.get_models():
        if not issubclass(model, PropertyBaseModel) or model._meta.abstract:
            continue
        model_field_names = {f.name for f in model._meta.fields}
        if "annualRent" not in model_field_names and "monthlyRent" not in model_field_names:
            continue
        avail = [fname for fname in model_field_names if fname in want_fields]
        for row in model.objects.values(*avail).iterator(chunk_size=2000):
            m = _extract_valid_investment_metrics(row, model.__name__)
            if m is None:
                continue
            for st_key in ({m["station"], ""} if m["station"] else {""}):
                rent_buckets[(m["pref"], m["city"], st_key, m["btype"])].append((m["rent_sqm"], m["area"]))
                if m["gross_yield"] is not None:
                    yield_buckets[(m["pref"], m["city"], st_key, m["atype"])].append(m["gross_yield"])
    return rent_buckets, yield_buckets


def sync_internal_db_rent_and_yield_potentials() -> dict[str, int]:
    """自社DBの全社収益物件レコードから実測賃料単価・実勢利回り中央値を集計してマスタへ同期する。"""
    rent_buckets, yield_buckets = _collect_internal_investment_buckets()
    jgb = _resolve_latest_jgb_yield()

    rent_rows: list[dict[str, Any]] = []
    for (pref, city, st_name, btype), samples in rent_buckets.items():
        med_sqm = round(median(s[0] for s in samples))
        med_area = round(median(s[1] for s in samples), 2)
        rent_rows.append({
            "prefecture": pref,
            "city": city,
            "station_name": st_name,
            "town_name": "",
            "building_type": btype,
            "layout_type": "all",
            "age_band": "all",
            "monthly_rent_yen": round(med_sqm * med_area),
            "standard_area_sqm": Decimal(f"{med_area:.2f}"),
            "rent_per_sqm": med_sqm,
            "sample_count": len(samples),
            "source": "internal_db",
        })

    cap_rows: list[dict[str, Any]] = []
    for (pref, city, st_name, atype), yields in yield_buckets.items():
        med_gross = round(float(median(yields)), 2)
        opex_pct = ASSET_CAP_ADJUSTMENTS.get(atype, (0.0, 20.0))[1]
        net_cap = round(med_gross * (1.0 - opex_pct / 100.0), 2)
        cap_rows.append({
            "prefecture": pref,
            "city": city,
            "station_name": st_name,
            "asset_type": atype,
            "expected_gross_yield": Decimal(f"{med_gross:.2f}"),
            "expected_net_cap_rate": Decimal(f"{net_cap:.2f}"),
            "standard_opex_ratio": Decimal(f"{opex_pct:.2f}"),
            "rental_vacancy_rate": None,
            "total_vacancy_rate": None,
            "jgb_spread_bps": round((net_cap - jgb) * 100),
            "demand_supply_score": None,
            "sample_count": len(yields),
            "survey_period": "",
            "source": "internal_db",
        })

    return {
        "rent_records": bulk_upsert_rent_records(rent_rows),
        "cap_rate_records": bulk_upsert_cap_rate_records(cap_rows),
    }


def _parse_raw_archive_blob(
    key: str,
    html_text: str,
    jgb_10y_yield: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    meta = parse_embedded_raw_meta(html_text)
    source_id = meta.get("source_id", "")
    pref = meta.get("prefecture", "")
    city = meta.get("city", "")
    station = meta.get("station", "")
    btype = meta.get("building_type", "all")

    if not source_id:
        m_src = re.search(r"source=([^/]+)/pref=([^/]+)/", key)
        if m_src:
            source_id, pref = m_src.group(1), m_src.group(2)

    if source_id == "suumo_soba":
        return parse_suumo_rent_table(html_text, pref, city, station, btype if btype != "all" else "mansion"), []
    if source_id == "athome_souba":
        return parse_athome_rent_page(html_text, pref, city, station, btype), []
    if source_id == "homes_price":
        return parse_homes_rent_table(html_text, pref, city, station), []
    if source_id == "homes_toushi":
        return [], parse_homes_toushi_page(html_text, pref, city, station)
    if source_id == "japan_reit":
        return [], parse_japan_reit_rimawari(html_text, jgb_10y_yield=jgb_10y_yield)
    return [], []


def reingest_from_gcs_raw_archive(storage_mgr: Any = None) -> dict[str, int]:
    """GCS `rag/raw/rent_mesh/` に保存された生HTML原本からDB構造化マスタを再構築する。"""
    crawler = MarketDataCrawler(storage_mgr=storage_mgr, min_interval_sec=0.0)
    raw_keys = [k for k in crawler.storage.list_files("rag/raw/rent_mesh/") if k.endswith(".html")]
    jgb = _resolve_latest_jgb_yield()

    rent_total = 0
    cap_total = 0
    for key in raw_keys:
        raw_html = crawler.storage.read_bytes(key).decode("utf-8", errors="replace")
        r_rows, c_rows = _parse_raw_archive_blob(key, raw_html, jgb)
        if r_rows:
            rent_total += bulk_upsert_rent_records(r_rows, gcs_raw_key=key)
        if c_rows:
            cap_total += bulk_upsert_cap_rate_records(c_rows, gcs_raw_key=key)

    return {
        "raw_files_processed": len(raw_keys),
        "rent_records_upserted": rent_total,
        "cap_rate_records_upserted": cap_total,
    }


def _crawl_and_store_single_page(
    crawler: MarketDataCrawler,
    url: str,
    source_id: str,
    prefecture: str,
    city: str = "",
    station: str = "",
    building_type: str = "all",
    jgb_10y_yield: float = 1.15,
) -> tuple[str | None, int, int]:
    html_text = crawler.fetch_html(url)
    if not html_text:
        return None, 0, 0

    r_rows, c_rows = _parse_raw_archive_blob(
        f"rag/raw/rent_mesh/source={source_id}/pref={prefecture}/",
        f'<!-- RENT_MESH_META: {{"source_id": "{source_id}", "prefecture": "{prefecture}", "city": "{city}", "station": "{station}", "building_type": "{building_type}"}} -->\n'
        + html_text,
        jgb_10y_yield,
    )
    archive_info = crawler.archive_raw_and_curated_to_gcs(
        url=url,
        html_content=html_text,
        source_id=source_id,
        prefecture=prefecture,
        city=city,
        station=station,
        building_type=building_type,
        extracted_count=len(r_rows) + len(c_rows),
    )
    r_cnt = bulk_upsert_rent_records(r_rows, gcs_raw_key=archive_info["raw_key"])
    c_cnt = bulk_upsert_cap_rate_records(c_rows, gcs_raw_key=archive_info["raw_key"])
    return html_text, r_cnt, c_cnt


def _suumo_slug(slug: str) -> str:
    """SUUMO家賃相場特有のURLスラッグ変換（北海道のみ `hokkaido_`）。"""
    return "hokkaido_" if slug == "hokkaido" else slug


def _crawl_suumo_for_prefecture(
    crawler: MarketDataCrawler,
    pref: str,
    slug: str,
    max_details: int,
) -> int:
    s_slug = _suumo_slug(slug)
    area_url = f"https://suumo.jp/chintai/soba/{s_slug}/area/"
    html_area, total_r, _ = _crawl_and_store_single_page(
        crawler, area_url, "suumo_soba", pref, building_type="all"
    )
    if not html_area or max_details <= 0:
        return total_r

    city_links = extract_portal_sublinks(html_area, area_url, rf"/chintai/soba/{s_slug}/sc_[a-z0-9_]+/")
    ts_types = [("1", "mansion"), ("2", "apartment"), ("3", "kodate")]
    fetched = 0
    for city_text, base_city_url in city_links:
        if fetched >= max_details:
            break
        clean_base = base_city_url.split("?")[0]
        clean_city = city_text.strip()
        if not clean_city.endswith(("区", "市", "町", "村")):
            continue
        for ts_code, btype in ts_types:
            if fetched >= max_details:
                break
            _, r_cnt, _ = _crawl_and_store_single_page(
                crawler, f"{clean_base}?ts={ts_code}", "suumo_soba", pref, city=clean_city, building_type=btype
            )
            total_r += r_cnt
            fetched += 1
    return total_r


def _crawl_suumo_stations_for_prefecture(
    crawler: MarketDataCrawler,
    pref: str,
    slug: str,
    max_lines: int = 4,
    max_stations_per_line: int = 5,
) -> int:
    s_slug = _suumo_slug(slug)
    ensen_url = f"https://suumo.jp/chintai/soba/{s_slug}/ensen/"
    html_ensen = crawler.fetch_html(ensen_url)
    if not html_ensen:
        return 0
    line_links = extract_portal_sublinks(html_ensen, ensen_url, rf"/chintai/soba/{s_slug}/en_[a-z0-9_]+/")
    total_r = 0
    for _, line_url in line_links[:max_lines]:
        html_line, r_cnt, _ = _crawl_and_store_single_page(
            crawler, line_url, "suumo_soba", pref, building_type="all"
        )
        total_r += r_cnt
        if not html_line:
            continue
        ek_links = extract_portal_sublinks(html_line, line_url, rf"/chintai/soba/{s_slug}/ek_\d+/")
        for st_label, ek_url in ek_links[:max_stations_per_line]:
            st_clean = normalize_station_label(st_label)
            if not st_clean or "物件" in st_clean:
                continue
            clean_ek = ek_url.split("?")[0]
            _, ek_cnt, _ = _crawl_and_store_single_page(
                crawler, f"{clean_ek}?ts=1", "suumo_soba", pref, station=st_clean, building_type="mansion"
            )
            total_r += ek_cnt
    return total_r


def _crawl_toushi_for_prefecture(
    crawler: MarketDataCrawler,
    pref: str,
    slug: str,
    max_details: int,
) -> int:
    pref_url = f"https://toushi.homes.co.jp/owner/{slug}/"
    html_pref, _, total_c = _crawl_and_store_single_page(crawler, pref_url, "homes_toushi", pref)
    if not html_pref or max_details <= 0:
        return total_c

    city_links = extract_portal_sublinks(html_pref, pref_url, rf"/owner/{slug}/city\d+/")
    for city_label, city_url in city_links[:max_details]:
        clean_city = city_label.strip()
        if not clean_city:
            continue
        _, _, c_cnt = _crawl_and_store_single_page(
            crawler, city_url, "homes_toushi", pref, city=clean_city
        )
        total_c += c_cnt
    return total_c


def _crawl_athome_and_homes_for_prefecture(
    crawler: MarketDataCrawler,
    pref: str,
    slug: str,
    max_details: int,
) -> int:
    total_r = 0
    homes_city_url = f"https://www.homes.co.jp/chintai/{slug}/city/price/"
    _, hm_cnt, _ = _crawl_and_store_single_page(crawler, homes_city_url, "homes_price", pref)
    total_r += hm_cnt

    athome_root_url = f"https://www.athome.co.jp/chintai/souba/{slug}/city/"
    html_at = crawler.fetch_html(athome_root_url)
    if html_at and max_details > 0:
        city_links = extract_portal_sublinks(html_at, athome_root_url, rf"/chintai/souba/{slug}/[a-z0-9\-]+-city/")
        for _, c_url in city_links[:max_details]:
            _, at_cnt, _ = _crawl_and_store_single_page(crawler, c_url, "athome_souba", pref)
            total_r += at_cnt
    return total_r


def crawl_live_portals_to_gcs_and_db(
    target_prefectures: list[str] | None = None,
    max_pages_per_source: int = 6,
    min_interval_sec: float = 0.8,
    storage_mgr: Any = None,
) -> dict[str, int]:
    """ポータル各社およびJ-REIT指標を実クロールし、GCS原本保存＋DB構造化反映を行う。"""
    crawler = MarketDataCrawler(storage_mgr=storage_mgr, min_interval_sec=min_interval_sec)
    jgb = _resolve_latest_jgb_yield()
    prefs = target_prefectures or list(PREFECTURE_MASTER_CONFIG.keys())

    rent_upserted = 0
    cap_upserted = 0

    _, _, reit_cnt = _crawl_and_store_single_page(
        crawler,
        "https://www.japan-reit.com/list/rimawari/",
        "japan_reit",
        "全国",
        jgb_10y_yield=jgb,
    )
    cap_upserted += reit_cnt

    for pref in prefs:
        if pref not in PREFECTURE_MASTER_CONFIG:
            continue
        slug = PREFECTURE_MASTER_CONFIG[pref][0]
        logger.info("Crawling market rent & cap-rate portals for %s (%s)...", pref, slug)
        rent_upserted += _crawl_suumo_for_prefecture(crawler, pref, slug, max_pages_per_source)
        rent_upserted += _crawl_suumo_stations_for_prefecture(
            crawler, pref, slug, max_lines=max(1, max_pages_per_source // 3), max_stations_per_line=3
        )
        rent_upserted += _crawl_athome_and_homes_for_prefecture(
            crawler, pref, slug, max(1, max_pages_per_source // 2)
        )
        cap_upserted += _crawl_toushi_for_prefecture(crawler, pref, slug, max_pages_per_source)

    return {
        "live_rent_upserted": rent_upserted,
        "live_cap_rate_upserted": cap_upserted,
    }


def sync_rent_and_cap_rate_potentials(
    enable_live_crawl: bool = False,
    target_prefectures: list[str] | None = None,
    max_pages_per_source: int = 6,
    min_interval_sec: float = 0.8,
) -> dict[str, Any]:
    """全データソース（e-Stat・JREI・自社DB集計・ポータル実クロール）を一括同期する。"""
    close_old_connections()
    estat_cnt = sync_estat_rent_baselines()
    jrei_cnt = sync_jrei_cap_rate_benchmarks()
    internal_stats = sync_internal_db_rent_and_yield_potentials()

    live_stats = {"live_rent_upserted": 0, "live_cap_rate_upserted": 0}
    if enable_live_crawl:
        live_stats = crawl_live_portals_to_gcs_and_db(
            target_prefectures=target_prefectures,
            max_pages_per_source=max_pages_per_source,
            min_interval_sec=min_interval_sec,
        )

    total_rent = RentMarketPotential.objects.count()
    total_cap = CapRateBenchmarkPotential.objects.count()
    logger.info(
        "✅ Rent & CapRate Potentials Sync Complete: Rent=%d rows, CapRate=%d rows",
        total_rent,
        total_cap,
    )
    return {
        "estat_rent_rows": estat_cnt,
        "jrei_cap_rate_rows": jrei_cnt,
        "internal_rent_rows": internal_stats["rent_records"],
        "internal_cap_rate_rows": internal_stats["cap_rate_records"],
        **live_stats,
        "total_rent_records": total_rent,
        "total_cap_rate_records": total_cap,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Sync nationwide rent market & cap-rate potentials")
    parser.add_argument("--live-crawl", action="store_true", help="Enable live portal crawling to GCS & DB")
    parser.add_argument(
        "--prefs",
        default="",
        help="Comma-separated prefectures for live crawl (empty = all 47 prefectures)",
    )
    parser.add_argument("--max-pages", type=int, default=6, help="Max detail pages per source/prefecture")
    parser.add_argument("--interval", type=float, default=0.8, help="Min interval seconds between requests")
    parser.add_argument("--reingest-gcs", action="store_true", help="Re-ingest raw HTML archive from GCS into DB")
    args = parser.parse_args()

    if args.reingest_gcs:
        res = reingest_from_gcs_raw_archive()
        logger.info("Re-ingested from GCS raw archive: %s", res)
        return

    pref_list = [p.strip() for p in args.prefs.split(",") if p.strip()] or None
    sync_rent_and_cap_rate_potentials(
        enable_live_crawl=args.live_crawl,
        target_prefectures=pref_list,
        max_pages_per_source=args.max_pages,
        min_interval_sec=args.interval,
    )


if __name__ == "__main__":
    main()
