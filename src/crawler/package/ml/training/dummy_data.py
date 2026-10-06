"""
学習用ダミーデータ生成モジュール (Issue #715)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _calculate_dummy_valuation_metrics(
    ptype: str, area: float, tochi_area: float, average_land_price: int, chikunen: float, rng: np.random.Generator
) -> dict[str, Any]:
    digest_volume_ratio = 0.0
    surplus_volume_potential = 0.0
    non_conforming_flag = 0
    if ptype in ["kodate", "apartment"]:
        digest_volume_ratio = (area / tochi_area) * 100.0 if tochi_area > 0 else 0.0
        surplus_volume_potential = max(0.0, 200.0 - digest_volume_ratio)
        if digest_volume_ratio > 200.0:
            non_conforming_flag = 1

    annual_rent = 0
    gross_yield = 0.0
    income_approach_value = 0
    if ptype in ["mansion", "apartment"]:
        gross_yield = float(rng.uniform(0.05, 0.15))
        annual_rent = int(area * rng.uniform(1.5, 3.5)) * 12
        income_approach_value = int(annual_rent / gross_yield) if gross_yield > 0 else 0

    cost_unit = 25.0 if ptype == "mansion" else 15.0
    lifespan = 47 if ptype == "mansion" else 22
    remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)

    if ptype == "mansion":
        cost_approach_value = (area * 0.2) * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)
    elif ptype == "tochi":
        cost_approach_value = tochi_area * (average_land_price / 10000.0)
    else:
        cost_approach_value = tochi_area * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)

    mkt_comparison_value = area * (average_land_price / 10000.0) * 0.95

    return {
        "digest_volume_ratio": digest_volume_ratio,
        "surplus_volume_potential": surplus_volume_potential,
        "non_conforming_flag": non_conforming_flag,
        "annual_rent": annual_rent,
        "gross_yield": gross_yield,
        "income_approach_value": income_approach_value,
        "cost_approach_value": cost_approach_value,
        "mkt_comparison_value": mkt_comparison_value,
    }


def _sample_dummy_areas(ptype: str, rng: np.random.Generator) -> tuple[float, float]:
    if ptype == "tochi":
        area = float(rng.uniform(50.0, 300.0))
        return area, area
    if ptype == "mansion":
        return float(rng.uniform(25.0, 100.0)), 0.0
    return float(rng.uniform(60.0, 150.0)), float(rng.uniform(70.0, 200.0))


def _resolve_dummy_type_attributes(ptype: str, area: float, rng: np.random.Generator) -> dict[str, Any]:
    if ptype == "mansion":
        return {
            "kanrihi": int(area * 200),
            "syuzen": int(area * 150),
            "max_youseki": 200.0,
            "max_kenpei": 60.0,
            "kouzou": "RC",
        }
    return {
        "kanrihi": 0,
        "syuzen": 0,
        "max_youseki": float(rng.choice([100.0, 150.0, 200.0])),
        "max_kenpei": float(rng.choice([40.0, 50.0, 60.0])),
        "kouzou": "木造" if ptype == "kodate" else "RC",
    }


def _generate_single_dummy_record(ptype: str, rng: np.random.Generator) -> dict[str, Any]:
    area, tochi_area = _sample_dummy_areas(ptype, rng)
    type_attrs = _resolve_dummy_type_attributes(ptype, area, rng)

    chikunen = float(rng.uniform(1.0, 45.0))
    walk_min = int(rng.integers(1, 20))
    pop_growth = float(rng.uniform(-1.0, 2.0))
    income = int(rng.integers(3000, 12000))
    passenger_volume = int(rng.integers(5000, 700000))
    average_land_price = int(rng.integers(150000, 3000000))
    interior_score = float(rng.uniform(1.5, 4.8))
    layout_score = float(rng.uniform(2.0, 4.8))

    metrics = _calculate_dummy_valuation_metrics(ptype, area, tochi_area, average_land_price, chikunen, rng)

    base_price = (area * (average_land_price / 10000.0)) - (chikunen * 40.0) - (walk_min * 50.0)
    area_multiplier = 1.0 + (income / 30000.0) + (passenger_volume / 5000000.0) + pop_growth * 0.05
    img_multiplier = 0.85 + (interior_score + layout_score) * 0.03

    if ptype == "apartment":
        base_price = metrics["annual_rent"] * 10

    price = max(1000, int(base_price * area_multiplier * img_multiplier + rng.normal(0, 300)))

    rand_val = rng.random()
    if rand_val < 0.02:
        price = 5
    elif rand_val < 0.04:
        area = 1.0

    return {
        "price": price,
        "area": area,
        "tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "walk_min": walk_min,
        "kanrihi": type_attrs["kanrihi"],
        "syuzen": type_attrs["syuzen"],
        "pop_growth": pop_growth,
        "income": income,
        "passenger_volume": passenger_volume,
        "average_land_price": average_land_price,
        "estimated_rosenka_price": int(average_land_price * 0.8),
        "estimated_fixed_asset_price": int(average_land_price * 0.7),
        "digest_volume_ratio": metrics["digest_volume_ratio"],
        "surplus_volume_potential": metrics["surplus_volume_potential"],
        "non_conforming_flag": metrics["non_conforming_flag"],
        "cost_approach_value": metrics["cost_approach_value"],
        "mkt_comparison_value": metrics["mkt_comparison_value"],
        "income_approach_value": metrics["income_approach_value"],
        "gross_yield": metrics["gross_yield"],
        "annual_rent": metrics["annual_rent"],
        "interior_score": interior_score,
        "layout_score": layout_score,
        "is_shin_taishin": 1 if chikunen <= 45.0 else 0,
        "flood_risk_level": int(rng.integers(0, 5)),
        "landslide_risk_level": int(rng.integers(0, 3)),
        "max_youseki": type_attrs["max_youseki"],
        "max_kenpei": type_attrs["max_kenpei"],
        "prefecture": "東京都",
        "city": "世田谷区",
        "station": "世田谷駅",
        "company": "mitsui",
        "kouzou": type_attrs["kouzou"],
        "maguchi": float(rng.uniform(2.0, 10.0)),
        "road_width": float(rng.uniform(3.0, 6.0)),
        "setback_ratio": 0.0,
        "actual_volume_limit": 200.0,
        "volume_digest_factor": 1.0,
        "road_condition_factor": 1.0,
        "frontage_penalty_factor": 1.0,
        "residual_land_value": 0.0,
        "road_direction": "南",
        "road_type": "公道",
        "road_structure": "中間地",
        "max_building_area": area * 0.6,
        "max_floor_area": area * 2.0,
        "kagechi_ratio": 1.0,
        "total_population": 150000,
        "income_growth_rate": 0.5,
        "land_price_growth_rate": 1.2,
        "effective_walk_min": float(walk_min),
        "population_density": 5000.0,
        "kouzou_lifespan_ratio": min(2.0, chikunen / 30.0),
        "is_shigaika_chousei": 0.0,
        "is_saikenchiku_fuka": 0.0,
        "rights_ratio": 1.0,
        "potential_floor_area": area if ptype == "mansion" else tochi_area * 2.0,
        "scale_discount": 1.0,
        "is_furuya": 1.0 if (ptype == "tochi" and rng.random() < 0.25) else 0.0,
        "has_demolition_condition": 0.0,
        "furuya_demolition_cost": 100.0 if (ptype == "tochi" and rng.random() < 0.25) else 0.0,
        "furuya_usable_value": 0.0,
        "furuya_option_value": 0.0,
        "plot_shadow_ratio": 0.0,
        "plot_aspect_ratio": 1.0,
        "plot_effective_ratio": 1.0,
        "plot_shape_penalty": 1.0,
        "plot_mic_diameter": 10.0,
        "plot_bottleneck_width": 10.0,
        "plot_solidity": 1.0,
        "plot_compactness": 1.0,
        "plot_nta_discount": 1.0,
        "plot_acute_angles": 0.0,
        "plot_flagpole_ratio": 0.0,
        "plot_shape_grade_num": 5.0,
        "plot_shape_score_100": 100.0,
        "zone_max_kenpei": 60.0,
        "zone_max_youseki": 200.0,
        "road_direction_angle": float(rng.choice([0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])),
        "sunlight_score": float(rng.uniform(0.75, 1.0)),
        "is_south_facing": float(rng.choice([0.0, 1.0])),
        "road_type_score": float(rng.choice([0.90, 0.95, 1.0])),
        "is_public_road": float(rng.choice([0.0, 1.0])),
        "is_private_road": float(rng.choice([0.0, 1.0])),
        "road_structure_score": float(rng.choice([0.75, 1.0, 1.06, 1.08, 1.15])),
        "is_corner_lot": float(rng.choice([0.0, 1.0])),
        "is_double_sided_road": float(rng.choice([0.0, 1.0])),
        "chimoku_score": float(rng.choice([0.70, 0.85, 0.95, 1.0])),
        "is_residential_chimoku": float(rng.choice([0.0, 1.0])),
        "floor_number": float(rng.integers(1, 10)),
        "total_floors": float(rng.integers(3, 15)),
        "floor_ratio": float(rng.uniform(0.1, 1.0)),
        "is_top_floor": float(rng.choice([0.0, 1.0])),
        "is_first_floor": float(rng.choice([0.0, 1.0])),
        "room_count": float(rng.integers(1, 5)),
        "has_ldk": float(rng.choice([0.0, 0.5, 1.0])),
        "is_studio": float(rng.choice([0.0, 1.0])),
        "kouzou_durability_rank": float(rng.choice([1.0, 2.0, 3.0, 4.0, 5.0])),
        "kouzou_fireproof_score": float(rng.choice([0.60, 0.70, 0.85, 1.00])),
        "is_rc_or_src": float(rng.choice([0.0, 1.0])),
        "is_wood": float(rng.choice([0.0, 1.0])),
        "company_tier": float(rng.choice([1.0, 2.0, 3.0])),
        "is_major_company": float(rng.choice([0.0, 1.0])),
        "is_residential_zone": float(rng.choice([0.0, 1.0])),
        "is_commercial_zone": float(rng.choice([0.0, 1.0])),
        "is_industrial_zone": float(rng.choice([0.0, 1.0])),
        "zone_rank": float(rng.choice([2.0, 3.0, 3.5, 4.0, 4.5, 5.0])),
        "shape_type_code": float(rng.choice([1.0, 2.0, 3.0, 4.0])),
        "is_regular_shape": float(rng.choice([0.0, 1.0])),
        "time_diff_months": float(rng.uniform(0.0, 24.0)),
        "macro_repi": 180.0,
        "macro_jgb_10y": 0.8,
        "macro_nikkei": 38000.0,
        "macro_reit": 1900.0,
        "macro_construction_cost": 125.0,
        "is_legacy_data": 0.0,
    }


def generate_dummy_data(ptype: str, num_records: int = 500) -> pd.DataFrame:
    """種別ごとのダミー学習データを生成"""
    logger.info("Generating dummy data for %s...", ptype)
    rng = np.random.default_rng(42)
    records = [_generate_single_dummy_record(ptype, rng) for _ in range(num_records)]
    return pd.DataFrame(records)
