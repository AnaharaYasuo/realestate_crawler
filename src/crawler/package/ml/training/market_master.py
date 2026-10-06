"""
取引事例比較マスタ構築モジュール (Issue #715)
"""

import logging
from typing import Any

import pandas as pd
from package.ml.features import _fallback_address, calculate_chikunen

logger = logging.getLogger(__name__)


def determine_eval_area(p: Any, ptype: str) -> float:
    """種別に応じた評価対象面積を取得"""
    try:
        if ptype == "tochi":
            val = getattr(p, "tochiMenseki", 0.0)
            return float(val) if val is not None else 0.0
        if ptype == "mansion":
            val = getattr(p, "senyuMenseki", 0.0)
            area = float(val) if val is not None else 0.0
            return 0.0 if area > 500.0 else area
        val = getattr(p, "tatemonoMenseki", 0.0)
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def extract_unit_price_record(p: Any, price: float, ptype: str) -> dict[str, Any] | None:
    """物件オブジェクトからエリア・平米単価レコードを抽出"""
    address1 = getattr(p, "address1", "") or ""
    address2 = getattr(p, "address2", "") or ""

    chikunengetsu = getattr(p, "chikunengetsu", None) or getattr(p, "chikunengetsuStr", None)
    chikunen = calculate_chikunen(chikunengetsu)
    eval_area = determine_eval_area(p, ptype)

    if eval_area > 0 and price > 0:
        return {
            "pref": address1,
            "city": address2,
            "ptype": ptype,
            "age_band": int(chikunen // 10),
            "unit_price": price / eval_area,
        }
    return None


def build_mkt_comparison_master(data_by_type: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str, str, int], float]:
    """
    ロードした全データからエリア別の「平均平米単価」マスタを作成
    groupby(...).to_dict() で高速・シンプル化
    """
    logger.info("Building market comparison master...")
    all_units = []

    for ptype, items in data_by_type.items():
        for item in items:
            rec = extract_unit_price_record(item["obj"], item["price"], ptype)
            if rec:
                all_units.append(rec)

    if not all_units:
        logger.info("Created market comparison master with 0 entries.")
        return {}

    df = pd.DataFrame(all_units)
    series = df.groupby(["pref", "city", "ptype", "age_band"])["unit_price"].mean()
    mkt_master = {
        (str(pref), str(city), str(ptype), int(age_band)): float(val)
        for (pref, city, ptype, age_band), val in series.items()
    }
    logger.info("Created market comparison master with %d entries.", len(mkt_master))
    return mkt_master


def _extract_unit_from_model_row(
    row_dict: dict[str, Any],
    ptype: str,
    area_field: str,
    duplicate_urls: set[str],
) -> dict[str, Any] | None:
    """単一行の辞書から平米単価レコードを抽出。無効データは None"""
    price = row_dict.get("price")
    if not price or price <= 0:
        return None
    page_url = row_dict.get("pageUrl")
    if page_url in duplicate_urls:
        return None
    area = row_dict.get(area_field)
    eval_area = float(area) if area is not None else 0.0
    if ptype == "mansion" and eval_area > 500.0:
        eval_area = 0.0
    if eval_area <= 0:
        return None

    pref = str(row_dict.get("address1") or "")
    city = str(row_dict.get("address2") or "")
    if not (pref and city):
        raw_addr = str(row_dict.get("address") or "")
        f_pref, f_city = _fallback_address(raw_addr, pref, city)
        pref = pref or f_pref
        city = city or f_city

    c_val = row_dict.get("chikunengetsu") or row_dict.get("chikunengetsuStr")
    chikunen = calculate_chikunen(c_val)
    price_man = float(price) / 10000.0
    return {
        "pref": pref,
        "city": city,
        "ptype": ptype,
        "age_band": int(chikunen // 10),
        "unit_price": price_man / eval_area,
    }


def _collect_units_from_single_model(
    model: Any,
    ptype: str,
    duplicate_urls: set[str],
) -> list[dict[str, Any]]:
    """単一モデルから values_list 経由で平米単価レコードリストを収集"""
    if ptype == "mansion":
        area_field = "senyuMenseki"
    elif ptype == "tochi":
        area_field = "tochiMenseki"
    else:
        area_field = "tatemonoMenseki"

    model_fields = {f.name for f in model._meta.get_fields()}
    query_fields = ["price", "pageUrl"]
    if "address1" in model_fields:
        query_fields.append("address1")
    if "address2" in model_fields:
        query_fields.append("address2")
    if "address" in model_fields:
        query_fields.append("address")

    if area_field in model_fields:
        query_fields.append(area_field)
    if "chikunengetsu" in model_fields:
        query_fields.append("chikunengetsu")
    elif "chikunengetsuStr" in model_fields:
        query_fields.append("chikunengetsuStr")

    try:
        qs = model.objects.order_by("pk").values_list(*query_fields)
        units = []
        for row in qs:
            row_dict = dict(zip(query_fields, row))
            rec = _extract_unit_from_model_row(row_dict, ptype, area_field, duplicate_urls)
            if rec:
                units.append(rec)
        return units
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not build market master for %s: %s", getattr(model, "__name__", "unknown"), e)
        return []


def build_market_master_from_models(
    models_by_type: dict[str, list[tuple[str, Any]]],
    duplicate_urls: set[str],
) -> dict[tuple[str, str, str, int], float]:
    """
    全社・全種別のモデルから軽量に values_list を走査して取引事例比較マスタを事前集計
    ORM モデルオブジェクトの大量生成を完全に回避
    """
    logger.info("Building market comparison master from models...")
    all_units = []

    for ptype, models_list in models_by_type.items():
        for _company, model in models_list:
            all_units.extend(_collect_units_from_single_model(model, ptype, duplicate_urls))

    if not all_units:
        logger.info("Created market comparison master with 0 entries.")
        return {}

    df = pd.DataFrame(all_units)
    series = df.groupby(["pref", "city", "ptype", "age_band"])["unit_price"].mean()
    mkt_master = {
        (str(pref), str(city), str(ptype), int(age_band)): float(val)
        for (pref, city, ptype, age_band), val in series.items()
    }
    logger.info("Created market comparison master with %d entries.", len(mkt_master))
    return mkt_master
