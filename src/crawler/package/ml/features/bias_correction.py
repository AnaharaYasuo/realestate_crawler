"""
特定物件種別のバイアス是正および非線形補正特徴量モジュール (Issue #1304, #1305, #1306)
"""
import math
from typing import Any
from .parsers import _get_attr, safe_float, parse_kouzou
from .constants import LIFESPAN


def _calculate_kodate_bias_features(
    chikunen: float,
    tatemono_area: float,
    kouzou_str: str,
    combined_text: str
) -> tuple[float, float]:
    """戸建て・アパート: 建物耐用年数超減価と解体控除 (Issue #1304)"""
    kouzou_cat = parse_kouzou(kouzou_str)
    legal_lifespan = float(LIFESPAN.get(kouzou_cat, 22))
    age = max(0.0, float(chikunen))

    if age <= legal_lifespan:
        dep_ratio = max(0.10, (legal_lifespan - age * 0.90) / legal_lifespan)
    else:
        over_years = age - legal_lifespan
        dep_ratio = max(0.05, 0.10 * math.exp(-0.03 * over_years))

    demolition_cost = 0.0
    is_furuya_text = any(k in combined_text for k in ["古家", "上物あり", "上物有", "解体"])
    if (age >= 30.0 or is_furuya_text) and "更地渡し" not in combined_text:
        b_area = max(50.0, float(tatemono_area or 80.0))
        demolition_cost = round(b_area * 1.5, 2)

    return round(dep_ratio, 4), demolition_cost


def _calculate_mansion_bias_features(
    property_obj: Any,
    chikunen: float
) -> tuple[float, float]:
    """マンション: 築古ヴィンテージ床と規模交差項 (Issue #1305)"""
    age = max(0.0, float(chikunen))
    vintage_floor = round(1.0 / (1.0 + math.exp(-0.15 * (age - 30.0))), 4) if age >= 25.0 else 0.0

    raw_units = _get_attr(property_obj, "soukosu", 0) or _get_attr(property_obj, "totalUnits", 0) or 0
    units = safe_float(raw_units, 0.0)
    log_units = math.log1p(max(0.0, units))
    scale_interaction = round(log_units * math.sqrt(max(1.0, age)), 4)

    return vintage_floor, scale_interaction


def _calculate_tochi_bias_features(
    average_land_price: float,
    is_shigaika_chousei: float
) -> float:
    """土地: 低路線価・低需要エリア非線形減価 (Issue #1306)"""
    land_price_val = float(average_land_price or 0.0)
    if land_price_val >= 50000.0 and is_shigaika_chousei < 0.5:
        return 1.0

    base_discount = max(0.20, (land_price_val / 50000.0) ** 0.5) if land_price_val > 0 else 0.20
    if is_shigaika_chousei >= 0.5:
        base_discount *= 0.50
    return round(base_discount, 4)


def calculate_bias_correction_features(
    property_obj: Any,
    property_type: str,
    chikunen: float,
    tatemono_area: float,
    average_land_price: float,
    kouzou_str: str,
    combined_text: str,
    is_shigaika_chousei: float,
) -> dict[str, float]:
    """
    本番実データ分析に基づく3大構造的バイアスを是正する特徴量を算出 (Issue #1304, #1305, #1306)
    """
    res = {
        "building_depreciation_ratio": 1.0,
        "demolition_cost_discount": 0.0,
        "mansion_vintage_floor": 0.0,
        "scale_vintage_interaction": 0.0,
        "low_demand_land_discount": 1.0,
    }

    if property_type in ("kodate", "apartment"):
        dep, demol = _calculate_kodate_bias_features(chikunen, tatemono_area, kouzou_str, combined_text)
        res["building_depreciation_ratio"] = dep
        res["demolition_cost_discount"] = demol

    if property_type == "mansion":
        v_floor, s_inter = _calculate_mansion_bias_features(property_obj, chikunen)
        res["mansion_vintage_floor"] = v_floor
        res["scale_vintage_interaction"] = s_inter

    if property_type in ("tochi", "kodate"):
        res["low_demand_land_discount"] = _calculate_tochi_bias_features(average_land_price, is_shigaika_chousei)

    return res
