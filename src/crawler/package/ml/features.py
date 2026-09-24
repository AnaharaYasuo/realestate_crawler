# -*- coding: utf-8 -*-
import datetime
import re
from decimal import Decimal
from typing import Dict, Tuple, Any, Optional
from package.utils.plot_shape_analyzer import analyze_plot_shape
from package.utils import converter

# 再調達単価 (万円/㎡) と法定耐用年数
REPLACEMENT_COSTS = {
    'RC': 25.0,
    'SRC': 25.0,
    'S': 20.0,
    'W': 15.0,
    'LS': 15.0,  # 軽量鉄骨
    'default': 18.0
}

LIFESPAN = {
    'RC': 47,
    'SRC': 47,
    'S': 34,
    'W': 22,
    'LS': 34,
    'default': 30
}

FEATURE_SETS = {
    "mansion": {
        "first": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "max_building_area", "max_floor_area",
            "kagechi_ratio", "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "floor_number", "total_floors", "floor_ratio", "is_top_floor", "is_first_floor",
            "room_count", "has_ldk", "is_studio",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ],
        "second": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "max_building_area", "max_floor_area",
            "kagechi_ratio", "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "floor_number", "total_floors", "floor_ratio", "is_top_floor", "is_first_floor",
            "room_count", "has_ldk", "is_studio",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ]
    },
    "kodate": {
        "first": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "room_count", "has_ldk", "total_floors",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ],
        "second": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "room_count", "has_ldk", "total_floors",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ]
    },
    "apartment": {
        "first": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "total_floors",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ],
        "second": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "total_floors",
            "kouzou_durability_rank", "kouzou_fireproof_score", "is_rc_or_src", "is_wood",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ]
    },
    "tochi": {
        "first": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "is_furuya", "has_demolition_condition", "furuya_demolition_cost", "furuya_usable_value", "furuya_option_value",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ],
        "second": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "road_direction_angle", "sunlight_score", "is_south_facing",
            "road_type_score", "is_public_road", "is_private_road",
            "road_structure_score", "is_corner_lot", "is_double_sided_road",
            "chimoku_score", "is_residential_chimoku",
            "company_tier", "is_major_company",
            "is_residential_zone", "is_commercial_zone", "is_industrial_zone", "zone_rank",
            "shape_type_code", "is_regular_shape",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "is_furuya", "has_demolition_condition", "furuya_demolition_cost", "furuya_usable_value", "furuya_option_value",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "plot_mic_diameter", "plot_bottleneck_width", "plot_solidity", "plot_compactness",
            "plot_nta_discount", "plot_acute_angles", "plot_flagpole_ratio", "plot_shape_grade_num",
            "plot_shape_score_100",
            "zone_max_kenpei", "zone_max_youseki",
            "time_diff_months", "macro_repi", "macro_jgb_10y", "macro_nikkei", "macro_reit", "macro_construction_cost", "is_legacy_data"
        ]
    }
}

def parse_kouzou(kouzou_str):
    """構造文字列から構造カテゴリを分類"""
    if not kouzou_str:
        return 'default'
    kouzou_str = kouzou_str.upper()
    if 'RC' in kouzou_str or '鉄筋コンクリート' in kouzou_str:
        return 'RC'
    if 'SRC' in kouzou_str or '鉄骨鉄筋' in kouzou_str:
        return 'SRC'
    if '鉄骨' in kouzou_str or '重量鉄骨' in kouzou_str or 'Ｓ造' in kouzou_str:
        if '軽量' in kouzou_str:
            return 'LS'
        return 'S'
    if '木' in kouzou_str or 'Ｗ造' in kouzou_str:
        return 'W'
    return 'default'


def parse_road_direction_features(direction_str: str) -> Dict[str, float]:
    """接道方角の数値化（方位角度数、日照採光スコア、南向きフラグ）"""
    d = str(direction_str or "")
    angles = {
        '北': 0.0, '北東': 45.0, '東': 90.0, '南東': 135.0,
        '南': 180.0, '南西': 225.0, '西': 270.0, '北西': 315.0
    }
    sunlight = {
        '南': 1.00, '南東': 0.95, '南西': 0.95, '東': 0.90,
        '西': 0.85, '北東': 0.80, '北西': 0.80, '北': 0.75
    }
    angle = 180.0
    sun = 0.88
    is_south = 0.0
    for k in ['南東', '南西', '北東', '北西', '南', '東', '西', '北']:
        if k in d:
            angle = angles[k]
            sun = sunlight[k]
            is_south = 1.0 if '南' in k else 0.0
            break
    return {
        "road_direction_angle": angle,
        "sunlight_score": sun,
        "is_south_facing": is_south
    }


def parse_road_type_features(type_str: str) -> Dict[str, float]:
    """道路種別の数値化（公道・私道・位置指定スコア）"""
    t = str(type_str or "")
    if "公道" in t:
        score = 1.00
        is_pub = 1.0
        is_pri = 0.0
    elif "位置指定" in t:
        score = 0.95
        is_pub = 0.0
        is_pri = 1.0
    elif "私道" in t:
        score = 0.90
        is_pub = 0.0
        is_pri = 1.0
    else:
        score = 0.90
        is_pub = 0.0
        is_pri = 0.0
    return {
        "road_type_score": score,
        "is_public_road": is_pub,
        "is_private_road": is_pri
    }


def parse_road_structure_features(struct_str: str) -> Dict[str, float]:
    """接道形態・状況の数値化（角地・両面道路プレミアム）"""
    s = str(struct_str or "")
    if "四方" in s:
        score = 1.15
        is_corner = 1.0
        is_double = 1.0
    elif "三方" in s:
        score = 1.10
        is_corner = 1.0
        is_double = 1.0
    elif "角地" in s or "準角地" in s:
        score = 1.08 if "角地" in s else 1.04
        is_corner = 1.0
        is_double = 0.0
    elif "両面" in s or "二方" in s:
        score = 1.06
        is_corner = 0.0
        is_double = 1.0
    elif any(k in s for k in ["袋地", "無道路", "通路"]):
        score = 0.75
        is_corner = 0.0
        is_double = 0.0
    else:
        score = 1.00
        is_corner = 0.0
        is_double = 0.0
    return {
        "road_structure_score": score,
        "is_corner_lot": is_corner,
        "is_double_sided_road": is_double
    }


def parse_chimoku_features(chimoku_str: str) -> Dict[str, float]:
    """地目の数値化（宅地・雑種地・農地・山林スコア）"""
    c = str(chimoku_str or "")
    if "宅地" in c:
        score = 1.00
        is_res = 1.0
    elif "雑種" in c:
        score = 0.95
        is_res = 0.0
    elif any(k in c for k in ["畑", "田", "農地"]):
        score = 0.85
        is_res = 0.0
    elif any(k in c for k in ["山林", "原野"]):
        score = 0.70
        is_res = 0.0
    else:
        score = 0.95
        is_res = 1.0 if not c else 0.0
    return {
        "chimoku_score": score,
        "is_residential_chimoku": is_res
    }


def parse_kouzou_features(kouzou_str: str) -> Dict[str, float]:
    """建物構造の数値化（耐久ランク、耐火スコア、RC/木造フラグ）"""
    k = str(kouzou_str or "").upper()
    cat = parse_kouzou(kouzou_str)
    if cat == 'SRC':
        rank = 5.0
        fireproof = 1.00
        is_rc = 1.0
        is_w = 0.0
    elif cat == 'RC':
        rank = 4.0
        fireproof = 1.00
        is_rc = 1.0
        is_w = 0.0
    elif cat == 'S':
        rank = 3.0
        fireproof = 0.80
        is_rc = 0.0
        is_w = 0.0
    elif cat == 'LS':
        rank = 2.0
        fireproof = 0.70
        is_rc = 0.0
        is_w = 0.0
    elif cat == 'W' or '木' in k:
        rank = 1.0
        fireproof = 0.60
        is_rc = 0.0
        is_w = 1.0
    else:
        rank = 2.5
        fireproof = 0.70
        is_rc = 0.0
        is_w = 0.0
    return {
        "kouzou_durability_rank": rank,
        "kouzou_fireproof_score": fireproof,
        "is_rc_or_src": is_rc,
        "is_wood": is_w
    }


def parse_company_features(company_str: str) -> Dict[str, float]:
    """不動産会社・分譲ブランドの数値化（大手ティア・ブランド力）"""
    c = str(company_str or "").lower()
    major_four = ["mitsui", "sumitomo", "nomura", "tokyu", "三井", "住友", "野村", "東急"]
    house_makers = ["misawa", "daiwa", "sekisui", "asahi", "ミサワ", "大和", "積水", "旭化成"]
    if any(m in c for m in major_four):
        tier = 3.0
        is_major = 1.0
    elif any(h in c for h in house_makers):
        tier = 2.0
        is_major = 0.0
    else:
        tier = 1.0
        is_major = 0.0
    return {
        "company_tier": tier,
        "is_major_company": is_major
    }


def parse_youto_zone_features(youto_str: str) -> Dict[str, float]:
    """用途地域規制の数値化（住居・商業・工業系フラグおよび住環境ランク）"""
    y = str(youto_str or "")
    is_res = 1.0 if any(k in y for k in ["住居", "低層", "中高層"]) else 0.0
    is_comm = 1.0 if any(k in y for k in ["商業", "近隣商業"]) else 0.0
    is_ind = 1.0 if any(k in y for k in ["工業", "準工業"]) else 0.0

    if "第1種低層" in y or "第１種低層" in y:
        rank = 5.0
    elif "第2種低層" in y or "第２種低層" in y:
        rank = 4.5
    elif "中高層" in y:
        rank = 4.0
    elif "住居" in y:
        rank = 3.5
    elif is_comm:
        rank = 3.0
    elif is_ind:
        rank = 2.0
    else:
        rank = 3.5
    return {
        "is_residential_zone": is_res,
        "is_commercial_zone": is_comm,
        "is_industrial_zone": is_ind,
        "zone_rank": rank
    }


def parse_madori_layout_features(madori_str: str, text: str = "") -> Dict[str, float]:
    """間取り・部屋数の数値化（部屋数、LDKフラグ、ワンルームフラグ）"""
    raw = (str(madori_str or "") + " " + str(text or "")).upper()
    room_count = 3.0
    has_ldk = 0.0
    is_studio = 0.0
    m = re.search(r'(\d+)\s*(?:R|K|DK|LDK|SLDK)?', raw)
    if m:
        room_count = float(m.group(1))
    if 'LDK' in raw:
        has_ldk = 1.0
    elif 'DK' in raw:
        has_ldk = 0.5
    elif '1R' in raw or 'ワンルーム' in raw:
        is_studio = 1.0
        room_count = 1.0
    return {
        "room_count": room_count,
        "has_ldk": has_ldk,
        "is_studio": is_studio
    }


def _extract_floor_number(floor_val: any, raw: str) -> float:
    m_fl = re.search(r'(\d{1,5})\s*階(?:建|部分)?', str(floor_val or ""))
    if m_fl:
        return float(m_fl.group(1))
    if floor_val:
        try:
            return float(floor_val)
        except Exception:
            pass
    m_fl2 = re.search(r'(\d{1,5})\s*階部分', raw)
    return float(m_fl2.group(1)) if m_fl2 else 0.0

def _extract_total_floors(total_floor_val: any, raw: str) -> float:
    m_tot = re.search(r'(?:(?:地上|地下)\s*)?(\d{1,5})\s*階建', str(total_floor_val or ""))
    if m_tot:
        return float(m_tot.group(1))
    if total_floor_val:
        try:
            return float(total_floor_val)
        except Exception:
            pass
    m_tot2 = re.search(r'(\d{1,5})\s*階建', raw)
    return float(m_tot2.group(1)) if m_tot2 else 0.0

def parse_floor_features(floor_val: any, total_floor_val: any, text: str = "") -> Dict[str, float]:
    """所在階・総階数・階高比率の数値化（最上階・1階フラグ）"""
    raw = f"{floor_val or ''} {total_floor_val or ''} {text or ''}"
    fl = _extract_floor_number(floor_val, raw)
    tot = _extract_total_floors(total_floor_val, raw)

    fl = max(1.0, fl) if fl > 0 else 3.0
    tot = max(fl, tot) if tot > 0 else max(fl, 5.0)
    return {
        "floor_number": fl,
        "total_floors": tot,
        "floor_ratio": round(fl / tot, 3),
        "is_top_floor": 1.0 if fl >= tot else 0.0,
        "is_first_floor": 1.0 if fl <= 1.0 else 0.0
    }

def _parse_wareki_date(text: str) -> Optional[datetime.date]:
    m = re.search(r'(昭和|平成|令和)(\d{1,2})年(?:(\d{1,2})月)?', text)
    if not m:
        return None
    era = m.group(1)
    year = int(m.group(2))
    month = int(m.group(3)) if m.group(3) else 1
    era_offsets = {'昭和': 1925, '平成': 1988, '令和': 2018}
    gregorian_year = era_offsets.get(era, 2000) + year
    try:
        return datetime.date(gregorian_year, month, 1)
    except Exception:
        return None

def _parse_seireki_date(text: str) -> Optional[datetime.date]:
    m = re.search(r'(\d{4})[年/\.-](\d{1,2})', text)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), 1)
        except Exception:
            pass
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None

def calculate_chikunen(chikunengetsu, base_date=None):
    """築年数を算出 (基準日を指定可能。文字列からのパースにも対応)"""
    if not base_date:
        base_date = datetime.date.today()
    if not chikunengetsu:
        return 20.0
    
    if isinstance(chikunengetsu, (datetime.date, datetime.datetime)):
        dt = chikunengetsu.date() if isinstance(chikunengetsu, datetime.datetime) else chikunengetsu
        return (base_date - dt).days / 365.25

    if isinstance(chikunengetsu, str):
        dt = _parse_wareki_date(chikunengetsu) or _parse_seireki_date(chikunengetsu)
        if dt:
            return (base_date - dt).days / 365.25
        return 20.0

    return 20.0

def _parse_float_from_str(val_str: str, default_val: any):
    if val_str.count('.') > 1:
        return default_val
    m_val = re.search(r'(\d+(?:\.\d+)?)', val_str)
    if not m_val:
        return default_val
    try:
        f_val = float(m_val.group(1))
        return default_val if f_val <= 0 and default_val is not None else f_val
    except (ValueError, TypeError):
        return default_val

def safe_float(val, default_val):
    if val is None:
        return default_val
    if isinstance(val, (int, float, Decimal)):
        f_val = float(val)
        return default_val if f_val <= 0 and default_val is not None else f_val
    if isinstance(val, str):
        return _parse_float_from_str(val.strip(), default_val)
    return default_val

# 全国47都道府県の標準的基準地価（住宅地/商業地, 円/㎡）
PREFECTURE_BASE_LAND_PRICES = {
    "東京都": (500000, 2500000),
    "神奈川県": (210000, 650000),
    "大阪府": (230000, 1300000),
    "愛知県": (150000, 600000),
    "京都府": (220000, 850000),
    "埼玉県": (140000, 420000),
    "兵庫県": (150000, 520000),
    "千葉県": (120000, 320000),
    "福岡県": (140000, 750000),
    "宮城県": (100000, 450000),
    "広島県": (100000, 380000),
    "静岡県": (70000, 180000),
    "滋賀県": (75000, 180000),
    "北海道": (50000, 220000),
    "奈良県": (80000, 200000),
    "岡山県": (65000, 180000),
    "熊本県": (65000, 220000),
    "沖縄県": (110000, 300000),
    "茨城県": (50000, 130000),
    "栃木県": (50000, 130000),
    "群馬県": (45000, 120000),
    "長野県": (40000, 95000),
    "岐阜県": (45000, 110000),
    "三重県": (45000, 110000),
    "新潟県": (35000, 80000),
    "富山県": (40000, 90000),
    "石川県": (55000, 160000),
    "福井県": (40000, 90000),
    "山梨県": (35000, 80000),
    "福島県": (40000, 95000),
    "山形県": (35000, 80000),
    "岩手県": (35000, 85000),
    "秋田県": (30000, 75000),
    "青森県": (30000, 75000),
    "鳥取県": (35000, 80000),
    "島根県": (30000, 75000),
    "山口県": (40000, 90000),
    "徳島県": (45000, 100000),
    "香川県": (55000, 140000),
    "愛媛県": (50000, 130000),
    "高知県": (45000, 110000),
    "佐賀県": (40000, 90000),
    "長崎県": (50000, 120000),
    "大分県": (45000, 110000),
    "宮崎県": (40000, 95000),
    "鹿児島県": (40000, 110000),
}

def _match_tokyo_district_price(pref_clean: str, city_clean: str) -> Optional[Tuple[int, int]]:
    if any(k in city_clean for k in ["千代田区", "中央区", "港区"]):
        return 2000000, 6500000
    if any(k in city_clean for k in ["渋谷区", "新宿区", "文京区", "目黒区"]):
        return 1300000, 3800000
    if any(k in city_clean for k in ["品川区", "世田谷区", "大田区", "杉並区", "中野区", "豊島区"]):
        return 800000, 2200000
    if "区" in city_clean and ("東京" in pref_clean or pref_clean == "東京都"):
        return 550000, 1400000
    return None

def _match_regional_hub_price(pref_clean: str, city_clean: str, base_res: int, base_comm: int) -> Optional[Tuple[int, int]]:
    if any(k in city_clean for k in ["北区", "中央区", "中区", "博多区", "東山区", "下京区", "西区"]):
        if any(p in pref_clean for p in ["大阪府", "京都府", "愛知県", "福岡県", "神奈川県", "兵庫県"]):
            return max(base_res * 2, 450000), max(base_comm * 2, 1800000)
    if any(k in city_clean for k in ["郡", "町", "村"]):
        return int(base_res * 0.45), int(base_comm * 0.45)
    return None

def _get_nationwide_base_land_price(prefecture: str, city: str = "") -> Tuple[int, int]:
    """
    全国47都道府県および市区町村別の基準地価（住宅地/商業地, 円/㎡）を動的算出
    """
    pref_clean = (prefecture or "").strip()
    city_clean = (city or "").strip()
    
    base_res, base_comm = 80000, 200000
    for p, vals in PREFECTURE_BASE_LAND_PRICES.items():
        if p in pref_clean or pref_clean in p:
            base_res, base_comm = vals
            break
            
    tokyo_price = _match_tokyo_district_price(pref_clean, city_clean)
    if tokyo_price:
        return tokyo_price
        
    regional_price = _match_regional_hub_price(pref_clean, city_clean, base_res, base_comm)
    if regional_price:
        return regional_price
        
    return base_res, base_comm

# グローバルキャッシュ変数
_muni_cache: Dict[Tuple[str, str], Any] = {}
_muni_pref_cache: Dict[str, list] = {}
_station_cache: Dict[str, Any] = {}
_lp_cache: Dict[Tuple[str, str, str], Any] = {}
_lp_pref_res_cache: Dict[str, list] = {}
_lp_pref_comm_cache: Dict[str, list] = {}
_hazard_cache: Dict[Tuple[str, str], Any] = {}
_zone_cache: Dict[str, Any] = {}
_macro_cache: Dict[str, Any] = {}

def _init_muni_cache(muni_cls):
    global _muni_cache, _muni_pref_cache
    if not _muni_cache:
        for m in muni_cls.objects.all():
            _muni_cache[(m.prefecture, m.city)] = m
            _muni_pref_cache.setdefault(m.prefecture, []).append(m)

def _init_lp_cache(lp_cls):
    global _lp_cache, _lp_pref_res_cache, _lp_pref_comm_cache
    if not _lp_cache:
        for lp in lp_cls.objects.all():
            _lp_cache[(lp.prefecture, lp.city, lp.land_use)] = lp
            if lp.land_use == 'residential':
                _lp_pref_res_cache.setdefault(lp.prefecture, []).append(lp)
            elif lp.land_use == 'commercial':
                _lp_pref_comm_cache.setdefault(lp.prefecture, []).append(lp)

def _init_misc_caches(station_cls, hazard_cls, zone_cls, macro_cls):
    global _station_cache, _hazard_cache, _zone_cache, _macro_cache
    if not _station_cache:
        for s in station_cls.objects.all():
            _station_cache[s.station_name] = s
    if not _hazard_cache:
        for hz in hazard_cls.objects.all():
            _hazard_cache[(hz.prefecture, hz.city)] = hz
    if not _zone_cache:
        for z in zone_cls.objects.all():
            _zone_cache[z.zone_name] = z
    _macro_cache.clear()
    for macro in macro_cls.objects.all():
        _macro_cache[macro.year_month] = macro

def _init_global_caches():
    """
    特徴量抽出のボトルネックを解消するため、
    全 Potential 関連マスタを一括でインメモリキャッシュします。
    """
    from package.models.evaluation import MunicipalPotential, StationPotential, LandPricePotential, HazardMapPotential, UrbanPlanningZonePotential, MacroEconomicIndex
    _init_muni_cache(MunicipalPotential)
    _init_lp_cache(LandPricePotential)
    _init_misc_caches(StationPotential, HazardMapPotential, UrbanPlanningZonePotential, MacroEconomicIndex)

    from django.db import connections
    try:
        connections.close_all()
    except Exception:
        pass

_load_all_potential_caches_once = _init_global_caches


def _get_attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)

def _clean_addr2(addr2: str) -> str:
    if addr2:
        m = re.match(r'^([^区市町村]+[区市町村])', addr2)
        if m:
            return m.group(1)
    return addr2

def _fallback_address(full_address: str, a1: str, a2: str):
    if a1 and a2:
        return a1, a2
    m = re.match(r'^(東京都|大阪府|京都府|北海道|[^県]+県)([^区市町]+[区市町])', full_address)
    if not m:
        return a1, a2
    return (a1 or m.group(1)), (a2 or m.group(2))

def _extract_clean_address(property_obj):
    address1 = str(_get_attr(property_obj, 'address1', '') or '')
    address2 = _clean_addr2(str(_get_attr(property_obj, 'address2', '') or ''))
    address1, address2 = _fallback_address(str(_get_attr(property_obj, 'address', '') or ''), address1, address2)
    station1 = str(_get_attr(property_obj, 'station1', '') or '')
    company = str(_get_attr(property_obj, 'company', 'unknown') or 'unknown')
    return address1, address2, station1, company

def _parse_date_value(val):
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        try:
            return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def _resolve_eval_base_date(base_date, prop_date):
    if not base_date:
        return prop_date or datetime.date.today()
    parsed = _parse_date_value(base_date)
    return parsed if parsed is not None else datetime.date.today()

def _check_is_legacy(prop_date, property_obj):
    if prop_date and prop_date < datetime.date(2025, 1, 1):
        return 1.0
    if bool(_get_attr(property_obj, 'is_legacy_data', False)):
        return 1.0
    if _get_attr(property_obj, 'isSoldout', 0) == 1:
        return 1.0
    return 0.0

def _resolve_eval_dates_and_diff(property_obj, base_date):
    raw_date = _get_attr(property_obj, 'inputDate', None) or _get_attr(property_obj, 'inputDateTime', None)
    prop_date = _parse_date_value(raw_date)
    eval_base_date = _resolve_eval_base_date(base_date, prop_date)
    ref_prop_date = prop_date or eval_base_date
    diff_days = (eval_base_date - ref_prop_date).days
    time_diff_months = max(0.0, round(float(diff_days) / 30.4375, 2))
    is_legacy = _check_is_legacy(prop_date, property_obj)
    return eval_base_date, ref_prop_date, time_diff_months, is_legacy

def _get_macro_record(ym: str):
    macro_rec = _macro_cache.get(ym)
    if not macro_rec and _macro_cache:
        sorted_keys = sorted(_macro_cache.keys())
        if ym < sorted_keys[0]:
            return _macro_cache[sorted_keys[0]]
        return _macro_cache[sorted_keys[-1]]
    return macro_rec

def _pick_macro_repi(property_type: str, repi_m: float, repi_k: float, repi_t: float) -> float:
    if property_type == 'kodate':
        return repi_k
    if property_type == 'tochi':
        return repi_t
    return repi_m

def _extract_macro_features(ref_prop_date, property_type):
    ym = f"{ref_prop_date.year:04d}-{ref_prop_date.month:02d}"
    macro_rec = _get_macro_record(ym)

    if macro_rec:
        repi_m = float(macro_rec.repi_mansion or 100.0)
        repi_k = float(macro_rec.repi_kodate or 100.0)
        repi_t = float(macro_rec.repi_tochi or 100.0)
        jgb = float(macro_rec.jgb_10y_yield or 0.0)
        nikkei = float(macro_rec.nikkei_225 or 25000.0)
        reit = float(macro_rec.tse_reit_index or 1800.0)
        const_cost = float(macro_rec.construction_cost_index or 100.0)
    else:
        repi_m, repi_k, repi_t = 100.0, 100.0, 100.0
        jgb = 0.5
        nikkei = 30000.0
        reit = 1800.0
        const_cost = 100.0

    macro_repi = _pick_macro_repi(property_type, repi_m, repi_k, repi_t)
    return macro_repi, jgb, nikkei, reit, const_cost

def _get_raw_chikunengetsu(property_obj):
    return (
        _get_attr(property_obj, 'chikunengetsu', None)
        or _get_attr(property_obj, 'builtYear', None)
        or _get_attr(property_obj, 'buildDate', None)
        or _get_attr(property_obj, 'chikunengetsuStr', None)
        or _get_attr(property_obj, 'kenchikuNengetsu', None)
        or _get_attr(property_obj, 'chikunen', None)
    )

def _calculate_chikunen_feature(property_obj, property_type, eval_base_date):
    chikunengetsu = _get_raw_chikunengetsu(property_obj)
    if not chikunengetsu:
        kouzou_raw = str(_get_attr(property_obj, 'kouzou', '') or _get_attr(property_obj, 'structure', ''))
        return 38.0 if ("木" in kouzou_raw or property_type == 'kodate') else 30.0
    return calculate_chikunen(chikunengetsu, eval_base_date)

def _extract_traffic_and_walk_min(property_obj):
    walk_min = _get_attr(property_obj, 'railwayWalkMinute1', None)
    raw_traffic = str(_get_attr(property_obj, 'traffic', '') or _get_attr(property_obj, 'koutsu', '') or '')
    bus_use = _get_attr(property_obj, 'busUse1', 0)
    
    bus_min = 0.0
    m_bus = re.search(r'(?:【バス】|バス|乗車)\s*(\d+)\s*分', raw_traffic)
    if m_bus:
        bus_min = safe_float(m_bus.group(1), 0.0)
        bus_use = 1
        
    bus_walk = _get_attr(property_obj, 'busWalkMinute1', None)
    if bus_walk is None:
        m_bwalk = re.search(r'(?:停歩|停 徒歩|バス停徒歩)\s*(\d+)\s*分', raw_traffic)
        bus_walk = safe_float(m_bwalk.group(1), 0.0) if m_bwalk else 0.0
    else:
        bus_walk = safe_float(bus_walk, 0.0)

    if walk_min is None:
        m_walk = re.search(r'(?:徒歩|歩)\s*(\d+)\s*分', raw_traffic)
        walk_min = safe_float(m_walk.group(1), 15) if m_walk else 15
    return int(walk_min), bus_min, bus_walk, bus_use

def _parse_setback_area(text: str) -> float:
    patterns = (
        r'(?:セットバック|後退)(?:面積)?(?:約)?\s*([\d.]+)\s*(?:㎡|平米|m2|ｍ２)',
        r'([\d.]+)\s*(?:㎡|平米|m2|ｍ２)\s*(?:のセットバック|の後退|セットバック要)',
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            val = safe_float(m.group(1), 0.0)
            if val > 0:
                return val
    return 0.0

def _collect_setback_candidate_texts(property_obj):
    texts = []
    setback_field = _get_attr(property_obj, 'setback', None)
    if setback_field:
        texts.append(str(setback_field))
    for attr in ('setsudou', 'remarks', 'tochiMensekiStr', 'note'):
        val = _get_attr(property_obj, attr, None)
        if val:
            texts.append(str(val))
    return texts

def _extract_setback_from_text(property_obj) -> float:
    for text in _collect_setback_candidate_texts(property_obj):
        area_val = _parse_setback_area(text)
        if area_val > 0:
            return area_val
    return 0.0

def _calculate_desk_setback(property_obj) -> float:
    maguchi_temp = _get_attr(property_obj, 'maguchi', None)
    road_width_temp = _get_attr(property_obj, 'roadWidth', None) or _get_attr(property_obj, 'douroHaba', None)
    raw_setsudou_temp = _get_attr(property_obj, 'setsudou', '') or ''
    
    if not road_width_temp and raw_setsudou_temp:
        m_width = re.search(r'(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou_temp)
        if m_width:
            road_width_temp = safe_float(m_width.group(1), 0.0)
            
    if not maguchi_temp and raw_setsudou_temp:
        m_maguchi = re.search(r'(?:間口|接面)\s*(?:約\s*)?(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou_temp)
        if m_maguchi:
            maguchi_temp = safe_float(m_maguchi.group(1), 0.0)
            
    maguchi_val_temp = safe_float(maguchi_temp, 6.0)
    road_width_val_temp = safe_float(road_width_temp, 4.0)
    
    if road_width_val_temp < 4.0:
        setback_width_temp = (4.0 - road_width_val_temp) / 2.0
        return maguchi_val_temp * setback_width_temp
    return 0.0

def _calculate_area_and_setback(property_obj, property_type):
    senyu_menseki = _get_attr(property_obj, 'senyuMenseki', 0.0)
    tatemono_menseki = _get_attr(property_obj, 'tatemonoMenseki', 0.0)
    tochi_menseki = _get_attr(property_obj, 'tochiMenseki', 0.0)
    
    area = float(senyu_menseki) if senyu_menseki else 0.0
    tatemono_area = float(tatemono_menseki) if tatemono_menseki else 0.0
    tochi_area = float(tochi_menseki) if tochi_menseki else 0.0
    
    if property_type == 'mansion' and area > 500.0:
        area = 70.0

    setback_area_temp = _extract_setback_from_text(property_obj)
    if setback_area_temp <= 0.0:
        setback_area_temp = _calculate_desk_setback(property_obj)

    setback_ratio_temp = 0.0
    if setback_area_temp > 0.0 and tochi_area > 0.0:
        setback_ratio_temp = min(1.0, setback_area_temp / tochi_area)
        
    tochi_area = tochi_area * (1.0 - setback_ratio_temp)
    return area, tatemono_area, tochi_area, setback_ratio_temp

def _query_municipal_potential(address1: str, address2: str):
    muni = _muni_cache.get((address1, address2))
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
        total_population = muni.total_population if muni.total_population is not None else 100000
        income_growth_rate = float(muni.income_growth_rate) if muni.income_growth_rate is not None else 0.0
        pop_density = float(muni.population_density) if muni.population_density is not None else 4000.0
        return pop_growth, income, total_population, income_growth_rate, pop_density

    muni_pref_vals = _muni_pref_cache.get(address1, [])
    if muni_pref_vals:
        n = len(muni_pref_vals)
        pop_growth = sum(float(x.population_growth_rate) for x in muni_pref_vals) / n
        income = int(sum(x.average_income for x in muni_pref_vals) / n)
        has_pop = [x.total_population for x in muni_pref_vals if x.total_population is not None]
        total_population = int(sum(has_pop) / len(has_pop)) if has_pop else 100000
        has_ig = [float(x.income_growth_rate) for x in muni_pref_vals if x.income_growth_rate is not None]
        income_growth_rate = (sum(has_ig) / len(has_ig)) if has_ig else 0.0
        has_pd = [float(x.population_density) for x in muni_pref_vals if x.population_density is not None]
        pop_density = (sum(has_pd) / len(has_pd)) if has_pd else 4000.0
        return pop_growth, income, total_population, income_growth_rate, pop_density

    return 0.0, 3000, 100000, 0.0, 4000.0

def _query_station_volume(station1: str) -> int:
    if not station1:
        return 10000
    station_clean = station1.replace("駅", "")
    station_pot = _station_cache.get(station_clean)
    return station_pot.passenger_volume if station_pot else 10000

def _calculate_effective_walk_min(walk_min: int, bus_use: int, bus_min: float, bus_walk: float, pop_density: float) -> float:
    walk_min_penalty_scale = max(0.4, min(1.0, 0.4 + 0.6 * (pop_density / 4000.0)))
    if bus_use or bus_min > 0:
        raw_access_min = float(bus_min * 1.5 + bus_walk)
        if raw_access_min < walk_min and bus_min > 0:
            raw_access_min = float(bus_min * 1.5 + walk_min)
        if raw_access_min <= 0:
            raw_access_min = float(walk_min)
    else:
        raw_access_min = float(walk_min)
    return raw_access_min * walk_min_penalty_scale

def _extract_slash_limit(text_str: str, is_youseki: bool) -> Optional[float]:
    if '/' not in text_str:
        return None
    parts = re.findall(r'(\d+(?:\.\d+)?)\s*%?', text_str)
    if len(parts) >= 2:
        try:
            return float(parts[1]) if is_youseki else float(parts[0])
        except (ValueError, TypeError):
            pass
    return None

def _extract_limit_by_regex(text_str: str, is_youseki: bool) -> Optional[float]:
    pattern = r'容積率?[^\d]{0,20}(\d{1,5}(?:\.\d{1,3})?)\s*%' if is_youseki else r'建[ぺペ]い率?[^\d]{0,20}(\d{1,5}(?:\.\d{1,3})?)\s*%'
    m = re.search(pattern, text_str)
    if m:
        return float(m.group(1))
    m_pct = re.search(r'(\d{1,5}(?:\.\d{1,3})?)\s*%', text_str)
    if m_pct:
        return float(m_pct.group(1))
    m_num = re.search(r'(\d{1,5}(?:\.\d{1,3})?)', text_str)
    if m_num:
        val = float(m_num.group(1))
        if 10.0 <= val <= 1500.0:
            return val
    return None

def _extract_limit_value(text, is_youseki=False):
    if not text:
        return None
    text_str = str(text)
    slash_val = _extract_slash_limit(text_str, is_youseki)
    if slash_val is not None:
        return slash_val
    return _extract_limit_by_regex(text_str, is_youseki)

def _find_zone_record_by_name(zone_name_prop: str):
    if not zone_name_prop:
        return None
    if zone_name_prop in _zone_cache:
        return _zone_cache[zone_name_prop]
    for name, z in _zone_cache.items():
        if name in str(zone_name_prop) or str(zone_name_prop) in name:
            return z
    return None

def _find_zone_record_by_keywords(check_text: str):
    keywords = [
        "第一種低層", "第二種低層", "第一種中高層", "第二種中高層",
        "第一種住居", "第二種住居", "準住居", "田園住居",
        "近隣商業", "商業", "準工業", "工業", "工業専用"
    ]
    for kw in keywords:
        if kw in check_text:
            for name, z in _zone_cache.items():
                if kw in name:
                    return z
    return None

def _find_first_attr(property_obj, attrs):
    for a in attrs:
        val = _get_attr(property_obj, a, None)
        if val is not None:
            return val
    return None

def _resolve_zone_from_record(zone_rec, max_kenpei, max_youseki):
    if not zone_rec:
        default_k = max_kenpei if max_kenpei is not None else 60.0
        default_y = max_youseki if max_youseki is not None else 200.0
        return max_kenpei, max_youseki, default_k, default_y
    zk = float(zone_rec.max_kenpei)
    zy = float(zone_rec.max_youseki)
    k = zk if max_kenpei is None else max_kenpei
    y = zy if max_youseki is None else max_youseki
    return k, y, zk, zy

def _fallback_zone_from_keywords(youseki_raw, zone_name_prop, max_kenpei, max_youseki, zk, zy):
    if max_youseki is not None and max_kenpei is not None:
        return max_kenpei, max_youseki, zk, zy
    check_text = f"{youseki_raw or ''} {zone_name_prop or ''}"
    kw_rec = _find_zone_record_by_keywords(check_text)
    if not kw_rec:
        return max_kenpei, max_youseki, zk, zy
    rec_k = float(kw_rec.max_kenpei)
    rec_y = float(kw_rec.max_youseki)
    k = rec_k if max_kenpei is None else max_kenpei
    y = rec_y if max_youseki is None else max_youseki
    return k, y, rec_k, rec_y

def _resolve_zone_limits(property_obj):
    youseki_raw = _find_first_attr(property_obj, ('youseki', 'yousekiStr', 'kenpeiYousekiStr', 'yousekiRitsu'))
    kenpei_raw = _find_first_attr(property_obj, ('kenpei', 'kenpeiStr', 'kenpeiYousekiStr', 'kenpeiRitsu'))
    max_youseki = _extract_limit_value(youseki_raw, is_youseki=True)
    max_kenpei = _extract_limit_value(kenpei_raw, is_youseki=False)

    zone_name_prop = _find_first_attr(property_obj, ('zone_name', 'youtoChiiki', 'youto'))
    zone_rec = _find_zone_record_by_name(zone_name_prop)
    max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki = _resolve_zone_from_record(zone_rec, max_kenpei, max_youseki)
    max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki = _fallback_zone_from_keywords(
        youseki_raw, zone_name_prop, max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki
    )

    max_youseki = 200.0 if max_youseki is None else max_youseki
    max_kenpei = 60.0 if max_kenpei is None else max_kenpei
    return max_youseki, max_kenpei, zone_max_kenpei, zone_max_youseki, zone_name_prop

def _calculate_commercial_weight(max_youseki: float) -> float:
    if max_youseki <= 150.0:
        return 0.0
    if max_youseki >= 450.0:
        return 1.0
    return (max_youseki - 150.0) / 300.0

def _get_land_price_stats(address1: str, address2: str, land_use: str, pref_cache: dict):
    lp = _lp_cache.get((address1, address2, land_use))
    if lp:
        growth = float(lp.land_price_growth_rate) if lp.land_price_growth_rate is not None else None
        return lp.average_land_price, lp.estimated_rosenka_price, lp.estimated_fixed_asset_price, growth

    pref_list = pref_cache.get(address1, [])
    if not pref_list:
        return None, None, None, None

    n = len(pref_list)
    price = sum(x.average_land_price for x in pref_list) / n
    rosenka = sum(x.estimated_rosenka_price for x in pref_list if x.estimated_rosenka_price is not None) / n
    fixed = sum(x.estimated_fixed_asset_price for x in pref_list if x.estimated_fixed_asset_price is not None) / n
    has_g = [float(x.land_price_growth_rate) for x in pref_list if x.land_price_growth_rate is not None]
    growth = (sum(has_g) / len(has_g)) if has_g else None
    return price, rosenka, fixed, growth

def _blend_land_prices(address1: str, address2: str, max_youseki: float):
    weight_comm = _calculate_commercial_weight(max_youseki)
    weight_res = 1.0 - weight_comm

    res_price, res_rosenka, res_fixed, res_growth = _get_land_price_stats(
        address1, address2, 'residential', _lp_pref_res_cache
    )
    comm_price, comm_rosenka, comm_fixed, comm_growth = _get_land_price_stats(
        address1, address2, 'commercial', _lp_pref_comm_cache
    )

    def blend_val(r_val, c_val, default):
        if r_val is not None and c_val is not None:
            return int(r_val * weight_res + c_val * weight_comm)
        if r_val is not None:
            return int(r_val)
        if c_val is not None:
            return int(c_val)
        return default

    def blend_float_val(r_val, c_val, default):
        if r_val is not None and c_val is not None:
            return float(r_val * weight_res + c_val * weight_comm)
        if r_val is not None:
            return float(r_val)
        if c_val is not None:
            return float(c_val)
        return default

    land_price_growth_rate = blend_float_val(res_growth, comm_growth, 0.0)
    def_res, def_comm = _get_nationwide_base_land_price(address1, address2)
    def_blend = blend_val(def_res, def_comm, 80000)
    average_land_price = blend_val(res_price, comm_price, def_blend)
    estimated_rosenka_price = blend_val(res_rosenka, comm_rosenka, int(average_land_price * 0.8))
    estimated_fixed_asset_price = blend_val(res_fixed, comm_fixed, int(average_land_price * 0.7))

    return average_land_price, estimated_rosenka_price, estimated_fixed_asset_price, land_price_growth_rate

def _calculate_mkt_comparison_value(
    mkt_comparison_master, address1, address2, property_type, chikunen, eval_area, average_land_price
):
    if not mkt_comparison_master:
        return eval_area * (average_land_price / 10000.0)
    age_band = int(chikunen // 10)
    key = (address1, address2, property_type, age_band)
    avg_unit_price = mkt_comparison_master.get(key)
    if avg_unit_price is None:
        keys_pref = [k for k in mkt_comparison_master.keys() if k[0] == address1 and k[2] == property_type and k[3] == age_band]
        avg_unit_price = (sum(mkt_comparison_master[k] for k in keys_pref) / len(keys_pref)) if keys_pref else 30.0
    return avg_unit_price * eval_area

def _resolve_cap_rate(gross_yield, income):
    if gross_yield is not None and float(gross_yield) > 0:
        return float(gross_yield) / 100.0
    if income > 7000:
        return 0.040
    if income > 4500:
        return 0.050
    return 0.06

def _calculate_income_approach_value(
    property_obj, property_type, income, average_land_price, potential_floor_area,
    eval_area, tochi_area, scale_discount
):
    gross_yield = _get_attr(property_obj, 'grossYield', None)
    annual_rent = _get_attr(property_obj, 'annualRent', None)
    cap_rate = _resolve_cap_rate(gross_yield, income)

    if annual_rent is not None and float(annual_rent) > 0:
        raw_rent = float(annual_rent)
        rent_man = (raw_rent / 10000.0) if raw_rent > 100000.0 else raw_rent
        return (rent_man * 0.85) / cap_rate, gross_yield, annual_rent

    unit_rent = max(1200.0, min(8000.0, average_land_price * 0.0018))
    if property_type == 'tochi':
        dev_floor_area = potential_floor_area * 0.80
        ann_rent_man = (dev_floor_area * unit_rent * 12.0) / 10000.0
        dev_cost = dev_floor_area * 22.0
        val = max(0.0, ((ann_rent_man * 0.85) / cap_rate) - dev_cost) * scale_discount
        if val <= 0:
            val = tochi_area * (average_land_price / 10000.0) * scale_discount * 0.7
        return val, gross_yield, annual_rent

    ann_rent_man = (eval_area * unit_rent * 12.0) / 10000.0
    val = ((ann_rent_man * 0.85) / cap_rate) * scale_discount
    return val, gross_yield, annual_rent

def _calculate_appraisal_values(
    property_obj, property_type, area, tatemono_area, tochi_area,
    chikunen, max_youseki, average_land_price, income, mkt_comparison_master,
    address1, address2
):
    scale_discount = max(0.05, float((1000.0 / tochi_area) ** 0.35)) if tochi_area > 1000.0 else 1.0
    potential_floor_area = area if property_type == 'mansion' else tochi_area * (max_youseki / 100.0)

    # Cost approach
    kouzou_str = _get_attr(property_obj, 'kouzou', '') or ''
    kouzou_cat = parse_kouzou(kouzou_str)
    cost_unit = REPLACEMENT_COSTS[kouzou_cat]
    lifespan = LIFESPAN[kouzou_cat]
    remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)

    if property_type == 'mansion':
        land_value = (area * 0.2) * (average_land_price / 10000.0)
        building_value = area * cost_unit * remaining_rate
    else:
        land_value = tochi_area * (average_land_price / 10000.0) * scale_discount
        building_value = tatemono_area * cost_unit * remaining_rate
    cost_approach_value = land_value + building_value

    # Market comparison
    eval_area = area if property_type == 'mansion' else tatemono_area
    eval_area = 50.0 if eval_area <= 0 else eval_area
    mkt_comparison_value = _calculate_mkt_comparison_value(
        mkt_comparison_master, address1, address2, property_type, chikunen, eval_area, average_land_price
    )

    income_approach_value, gross_yield, annual_rent = _calculate_income_approach_value(
        property_obj, property_type, income, average_land_price, potential_floor_area,
        eval_area, tochi_area, scale_discount
    )

    return potential_floor_area, scale_discount, cost_approach_value, mkt_comparison_value, income_approach_value, gross_yield, annual_rent

def _fallback_road_dimensions(raw_setsudou, road_width, maguchi):
    if not raw_setsudou:
        return safe_float(road_width, 4.0), safe_float(maguchi, 6.0)
    if not road_width:
        m_width = re.search(r'(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou)
        if m_width:
            road_width = safe_float(m_width.group(1), None)
    if not maguchi:
        m_maguchi = re.search(r'(?:間口|接面)\s*(?:約\s*)?(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou)
        if m_maguchi:
            maguchi = safe_float(m_maguchi.group(1), None)
    return safe_float(road_width, 4.0), safe_float(maguchi, 6.0)

def _fallback_road_classification(raw_setsudou, direction_str, type_str):
    if not raw_setsudou:
        return direction_str, type_str
    if not direction_str:
        for d in ("北東", "北西", "南東", "南西", "東", "西", "南", "北"):
            if d in raw_setsudou:
                direction_str = d
                break
    if not type_str:
        if "公道" in raw_setsudou:
            type_str = "公道"
        elif "私道" in raw_setsudou:
            type_str = "私道"
    return direction_str, type_str

def _extract_road_specs(property_obj):
    maguchi = _get_attr(property_obj, 'maguchi', None)
    road_width = _find_first_attr(property_obj, ('roadWidth', 'douroHaba'))
    road_dir = str(_find_first_attr(property_obj, ('roadDirection', 'douroMuki')) or '')
    road_type = str(_find_first_attr(property_obj, ('roadType', 'douroKubun')) or '')
    road_structure = str(_find_first_attr(property_obj, ('roadStructure', 'setsudou')) or '')
    chimoku = str(_get_attr(property_obj, 'chimoku', '') or '')
    raw_setsudou = str(_get_attr(property_obj, 'setsudou', '') or '')

    road_width_val, maguchi_val = _fallback_road_dimensions(raw_setsudou, road_width, maguchi)
    road_dir, road_type = _fallback_road_classification(raw_setsudou, road_dir, road_type)
    return maguchi_val, road_width_val, road_dir, road_type, road_structure, chimoku

def _calculate_road_factors(tochi_area, maguchi_val, road_width_val, road_direction_str, road_structure_str, youto_chiiki, max_youseki):
    is_commercial = any(x in (youto_chiiki or '') for x in ("商業", "近隣商業", "工業", "準工業", "工業専用"))
    multiplier = 0.6 if is_commercial else 0.4
    road_volume_limit = road_width_val * multiplier * 100.0
    actual_volume_limit = min(max_youseki, road_volume_limit)

    volume_digest_factor = 1.0
    if "北" in road_direction_str and road_width_val >= 4.0:
        volume_digest_factor = 1.15
    elif "南" in road_direction_str:
        est_depth = tochi_area / maguchi_val if maguchi_val > 0 else 10.0
        if est_depth < 10.0:
            volume_digest_factor = 0.85

    road_condition_factor = 1.0
    if any(x in road_structure_str for x in ("角地", "準角地", "三方", "四方")):
        road_condition_factor = 1.05
    elif any(x in road_structure_str for x in ("二方", "両面道路")):
        road_condition_factor = 1.03

    frontage_penalty_factor = 1.0
    if maguchi_val < 2.0:
        frontage_penalty_factor = 0.25
    elif maguchi_val < 4.0:
        frontage_penalty_factor = 0.90

    return actual_volume_limit, volume_digest_factor, road_condition_factor, frontage_penalty_factor

def _calculate_tochi_appraisal_factors(
    property_obj, property_type, tochi_area, max_youseki, average_land_price, setback_ratio_temp
):
    if property_type not in ['tochi', 'kodate', 'apartment']:
        return (
            6.0, 4.0, 0.0, max_youseki,
            1.0, 1.0, 1.0,
            0.0, "", "", "", ""
        )

    (
        maguchi_val, road_width_val, road_direction_str,
        road_type_str, road_structure_str, chimoku_str
    ) = _extract_road_specs(property_obj)
    youto = _get_attr(property_obj, 'youtoChiiki', '') or ''
    (
        actual_volume_limit, volume_digest_factor,
        road_condition_factor, frontage_penalty_factor
    ) = _calculate_road_factors(
        tochi_area, maguchi_val, road_width_val, road_direction_str, road_structure_str, youto, max_youseki
    )
    residual_land_value = tochi_area * (average_land_price / 10000.0) * volume_digest_factor * road_condition_factor * frontage_penalty_factor

    return (
        maguchi_val, road_width_val, setback_ratio_temp, actual_volume_limit,
        volume_digest_factor, road_condition_factor, frontage_penalty_factor,
        residual_land_value, road_direction_str, road_type_str, road_structure_str, chimoku_str
    )

def _build_shape_metrics_features(shape_metrics):
    shape_code_map = {'regular': 1.0, 'irregular': 2.0, 'slender': 3.0, 'flagpole': 4.0}
    s_type = getattr(shape_metrics, 'shape_type', 'regular')
    return {
        "kagechi_ratio": shape_metrics.shadow_area_ratio,
        "plot_shadow_ratio": shape_metrics.shadow_area_ratio,
        "plot_aspect_ratio": shape_metrics.mir_aspect_ratio,
        "plot_effective_ratio": shape_metrics.mir_effective_ratio,
        "plot_shape_penalty": shape_metrics.shape_penalty_score,
        "plot_mic_diameter": shape_metrics.mic_diameter,
        "plot_bottleneck_width": shape_metrics.bottleneck_width,
        "plot_solidity": shape_metrics.solidity,
        "plot_compactness": shape_metrics.compactness,
        "plot_nta_discount": shape_metrics.nta_composite_discount,
        "plot_acute_angles": float(shape_metrics.acute_angle_count),
        "plot_flagpole_ratio": shape_metrics.flagpole_passage_ratio,
        "plot_shape_grade_num": float(shape_metrics.shape_grade_num),
        "plot_shape_score_100": shape_metrics.shape_score_100,
        "shape_type_code": shape_code_map.get(s_type, 1.0),
        "is_regular_shape": 1.0 if s_type == 'regular' else 0.0
    }, shape_metrics.shape_penalty_score


def _build_fallback_shape_features(is_hatasao: bool, is_fuseigei: bool, kagechi_ratio: float):
    shape_penalty = round(max(0.60, min(1.0, 1.0 - (kagechi_ratio * 0.35))), 4)
    if is_hatasao:
        s_type = 'flagpole'
    elif is_fuseigei:
        s_type = 'irregular'
    else:
        s_type = 'regular'
    shape_code_map = {'regular': 1.0, 'irregular': 2.0, 'slender': 3.0, 'flagpole': 4.0}
    return {
        "kagechi_ratio": kagechi_ratio,
        "plot_shadow_ratio": kagechi_ratio,
        "plot_aspect_ratio": 0.5 if is_fuseigei else 1.0,
        "plot_effective_ratio": max(0.0, 1.0 - kagechi_ratio),
        "plot_shape_penalty": shape_penalty,
        "plot_mic_diameter": 6.0 if is_fuseigei else 10.0,
        "plot_bottleneck_width": 4.0 if is_fuseigei else 10.0,
        "plot_solidity": 0.85 if is_fuseigei else 1.0,
        "plot_compactness": 0.70 if is_fuseigei else 1.0,
        "plot_nta_discount": shape_penalty,
        "plot_acute_angles": 0.0,
        "plot_flagpole_ratio": 0.0,
        "plot_shape_grade_num": 3.0 if is_fuseigei else 5.0,
        "plot_shape_score_100": round(shape_penalty * 100.0, 1),
        "shape_type_code": shape_code_map.get(s_type, 1.0),
        "is_regular_shape": 1.0 if s_type == 'regular' else 0.0
    }, shape_penalty


def _calculate_plot_shape_features(
    property_obj, property_type, cost_approach_value, mkt_comparison_value, residual_land_value
):
    biko_text = _get_attr(property_obj, 'biko', '') or ''
    tochi_text = _get_attr(property_obj, 'tochikenri', '') or ''
    is_hatasao = any(x in str(biko_text) or x in str(tochi_text) for x in ["旗竿", "路地状", "敷地延長", "敷延"])
    is_fuseigei = any(x in str(biko_text) or x in str(tochi_text) for x in ["不整形", "変形地", "台形地", "袋地"])

    kagechi_ratio = safe_float(_get_attr(property_obj, 'kagechi_ratio', None), None)
    if kagechi_ratio is None:
        if is_hatasao:
            kagechi_ratio = 0.25
        elif is_fuseigei:
            kagechi_ratio = 0.15
        else:
            kagechi_ratio = 0.0

    plot_vertices = _get_attr(property_obj, 'plot_vertices', None)
    shape_metrics = analyze_plot_shape(plot_vertices) if plot_vertices and len(plot_vertices) >= 3 else None

    if shape_metrics:
        shape_feats, plot_shape_penalty = _build_shape_metrics_features(shape_metrics)
    else:
        shape_feats, plot_shape_penalty = _build_fallback_shape_features(is_hatasao, is_fuseigei, kagechi_ratio)

    if property_type in ['tochi', 'kodate']:
        cost_approach_value = round(cost_approach_value * plot_shape_penalty, 2)
        mkt_comparison_value = round(mkt_comparison_value * plot_shape_penalty, 2)
        if residual_land_value > 0:
            residual_land_value = round(residual_land_value * plot_shape_penalty, 2)

    return shape_feats, cost_approach_value, mkt_comparison_value, residual_land_value

def _extract_combined_text_for_prop(property_obj):
    raw_html_content = _get_attr(property_obj, 'raw_html', '') or _get_attr(property_obj, 'rawHtml', '') or _get_attr(property_obj, 'detail_html', '') or _get_attr(property_obj, 'page_html', '') or ''
    tochikenri = _get_attr(property_obj, 'tochikenri', '') or ''
    biko_val = _get_attr(property_obj, 'biko', '') or ''
    kuiki = _get_attr(property_obj, 'kuiki', '') or ''
    youto = _get_attr(property_obj, 'youtoChiiki', '') or ''
    prop_name = _get_attr(property_obj, 'propertyName', '') or ''
    setsudou_text = _get_attr(property_obj, 'setsudou', '') or _get_attr(property_obj, 'roadStructure', '') or ''
    notes_val = _get_attr(property_obj, 'notes', '') or _get_attr(property_obj, 'bikou', '') or ''
    genkyo_val = _get_attr(property_obj, 'genkyo', '') or ''

    all_text_list = [raw_html_content, tochikenri, biko_val, kuiki, youto, prop_name, setsudou_text, notes_val, genkyo_val]
    return " ".join([str(x) for x in all_text_list if x])

def _evaluate_furuya(
    combined_text, property_type, tochi_area, tatemono_area, average_land_price, scale_discount,
    is_saikenchiku_fuka, cost_approach_value, income_approach_value, residual_land_value
):
    furuya_keywords = [
        "古家あり", "古家有", "古家付", "古家建", "上物あり", "上物有", "上物付",
        "古家解体", "建物あり", "建物有", "現況：古家", "現況古家", "上物解体", "古家付売地"
    ]
    if not any(k in combined_text for k in furuya_keywords):
        return {
            "is_furuya": 0.0,
            "has_demolition_condition": 0.0,
            "furuya_demolition_cost": 0.0,
            "furuya_usable_value": 0.0,
            "furuya_option_value": 0.0,
            "cost_approach_value": cost_approach_value,
            "income_approach_value": income_approach_value,
            "residual_land_value": residual_land_value,
        }

    is_furuya = 1.0
    demolition_cond_keywords = [
        "更地渡し", "解体更地渡し", "解体後引渡", "更地引渡",
        "売主負担にて解体", "売主負担で解体", "売主にて解体", "売主側で解体"
    ]
    has_demolition_condition = 1.0 if any(k in combined_text for k in demolition_cond_keywords) else 0.0

    m_bldg = re.search(r'(?:延床|建物)(?:面積)?[:：約]?\s*([\d.]+)\s*(?:㎡|平米|m2|ｍ２)', combined_text)
    furuya_bldg_area = safe_float(m_bldg.group(1), 0.0) if m_bldg else 0.0
    if furuya_bldg_area <= 0.0:
        furuya_bldg_area = safe_float(tatemono_area, 0.0)
    if furuya_bldg_area <= 0.0:
        furuya_bldg_area = 80.0

def _determine_demolish_unit(combined_text: str) -> float:
    if "鉄骨" in combined_text:
        return 1.8
    if any(x in combined_text for x in ["RC", "鉄筋"]):
        return 2.5
    return 1.4


def _calculate_furuya_values(
    furuya_bldg_area: float, average_land_price: float, tochi_area: float,
    scale_discount: float, is_saikenchiku_fuka: float, furuya_demolition_cost: float
) -> Tuple[float, float]:
    unit_rent_monthly = max(1200.0, min(8000.0, average_land_price * 0.0018))
    est_monthly_rent_man = max(4.0, min(25.0, (unit_rent_monthly * furuya_bldg_area * 0.70) / 10000.0))
    est_annual_noi_man = est_monthly_rent_man * 12.0 * 0.80
    cap_rate_furuya = 0.10 if is_saikenchiku_fuka >= 0.5 else 0.08
    gross_furuya_val = est_annual_noi_man / cap_rate_furuya
    renov_cost = furuya_bldg_area * 3.0

    if is_saikenchiku_fuka >= 0.5:
        furuya_usable_value = round(max(0.0, gross_furuya_val - renov_cost) + tochi_area * (average_land_price / 10000.0) * 0.25, 2)
    else:
        furuya_usable_value = round(max(0.0, gross_furuya_val - renov_cost), 2)

    saikenchiku_land_factor = 0.20 if is_saikenchiku_fuka >= 0.5 else 1.0
    clean_land_val = max(0.0, tochi_area * (average_land_price / 10000.0) * scale_discount * saikenchiku_land_factor - furuya_demolition_cost)
    furuya_option_value = round(max(0.0, furuya_usable_value - clean_land_val), 2)
    return furuya_usable_value, furuya_option_value


def _adjust_tochi_furuya_values(
    cost_approach_value: float, income_approach_value: float, residual_land_value: float,
    is_saikenchiku_fuka: float, furuya_usable_value: float, furuya_demolition_cost: float,
    furuya_option_value: float
) -> Tuple[float, float, float]:
    if is_saikenchiku_fuka >= 0.5:
        c_val = furuya_usable_value
        i_val = max(income_approach_value, furuya_usable_value)
    else:
        c_val = max(0.0, cost_approach_value - furuya_demolition_cost) + (furuya_option_value * 0.5)
        i_val = max(income_approach_value, furuya_usable_value) if furuya_usable_value > 0 else income_approach_value
    r_val = max(0.0, residual_land_value - furuya_demolition_cost) if furuya_demolition_cost > 0 else residual_land_value
    return c_val, i_val, r_val


def _evaluate_furuya(
    combined_text, property_type, tochi_area, tatemono_area, average_land_price, scale_discount,
    is_saikenchiku_fuka, cost_approach_value, income_approach_value, residual_land_value
):
    furuya_keywords = [
        "古家あり", "古家有", "古家付", "古家建", "上物あり", "上物有", "上物付",
        "古家解体", "建物あり", "建物有", "現況：古家", "現況古家", "上物解体", "古家付売地"
    ]
    if not any(k in combined_text for k in furuya_keywords):
        return {
            "is_furuya": 0.0,
            "has_demolition_condition": 0.0,
            "furuya_demolition_cost": 0.0,
            "furuya_usable_value": 0.0,
            "furuya_option_value": 0.0,
            "cost_approach_value": cost_approach_value,
            "income_approach_value": income_approach_value,
            "residual_land_value": residual_land_value,
        }

    is_furuya = 1.0
    demolition_cond_keywords = [
        "更地渡し", "解体更地渡し", "解体後引渡", "更地引渡",
        "売主負担にて解体", "売主負担で解体", "売主にて解体", "売主側で解体"
    ]
    has_demolition_condition = 1.0 if any(k in combined_text for k in demolition_cond_keywords) else 0.0

    m_bldg = re.search(r'(?:延床|建物)(?:面積)?[:：約]?\s*([\d.]+)\s*(?:㎡|平米|m2|ｍ２)', combined_text)
    furuya_bldg_area = safe_float(m_bldg.group(1), 0.0) if m_bldg else 0.0
    if furuya_bldg_area <= 0.0:
        furuya_bldg_area = safe_float(tatemono_area, 0.0)
    if furuya_bldg_area <= 0.0:
        furuya_bldg_area = 80.0

    unit_demolish = _determine_demolish_unit(combined_text)
    if has_demolition_condition >= 0.5 or is_saikenchiku_fuka >= 0.5:
        furuya_demolition_cost = 0.0
    else:
        furuya_demolition_cost = round(furuya_bldg_area * unit_demolish, 2)

    furuya_usable_value, furuya_option_value = _calculate_furuya_values(
        furuya_bldg_area, average_land_price, tochi_area, scale_discount, is_saikenchiku_fuka, furuya_demolition_cost
    )

    if property_type == 'tochi':
        cost_approach_value, income_approach_value, residual_land_value = _adjust_tochi_furuya_values(
            cost_approach_value, income_approach_value, residual_land_value,
            is_saikenchiku_fuka, furuya_usable_value, furuya_demolition_cost, furuya_option_value
        )

    return {
        "is_furuya": is_furuya,
        "has_demolition_condition": has_demolition_condition,
        "furuya_demolition_cost": furuya_demolition_cost,
        "furuya_usable_value": furuya_usable_value,
        "furuya_option_value": furuya_option_value,
        "cost_approach_value": cost_approach_value,
        "income_approach_value": income_approach_value,
        "residual_land_value": residual_land_value,
    }

def _extract_legal_and_furuya_features(
    property_type, combined_text, chikunen, tochi_area, tatemono_area,
    average_land_price, scale_discount, cost_approach_value, income_approach_value, residual_land_value
):
    combined_text_lower = combined_text.lower()
    is_shigaika_chousei = 1.0 if ("調整区域" in combined_text or "市街化調整" in combined_text) else 0.0
    is_saikenchiku_fuka = 1.0 if ("再建築不可" in combined_text) else 0.0

    rights_ratio = 1.0
    if "底地" in combined_text_lower or "貸地" in combined_text_lower:
        rights_ratio = 0.20
    elif "定期" in combined_text_lower or "定借" in combined_text_lower:
        remaining_ratio = max(0.20, (50 - chikunen) / 50.0) if chikunen > 0 else 0.50
        rights_ratio = 0.70 * remaining_ratio
    elif "借地" in combined_text_lower or "賃借" in combined_text_lower:
        rights_ratio = 0.65

    res = _evaluate_furuya(
        combined_text, property_type, tochi_area, tatemono_area, average_land_price, scale_discount,
        is_saikenchiku_fuka, cost_approach_value, income_approach_value, residual_land_value
    )
    res["is_shigaika_chousei"] = is_shigaika_chousei
    res["is_saikenchiku_fuka"] = is_saikenchiku_fuka
    res["rights_ratio"] = rights_ratio
    return res

def _resolve_building_master_obj(property_obj):
    bm_obj = _get_attr(property_obj, 'building_master', None)
    if bm_obj:
        return bm_obj
    try:
        from package.models.building_master import BuildingMaster
        from package.utils.building_resolver import normalize_building_name, normalize_building_address
        p_name = _get_attr(property_obj, 'propertyName', '') or _get_attr(property_obj, 'title', '') or ''
        p_addr = _get_attr(property_obj, 'address', '') or ''
        n_name = normalize_building_name(p_name)
        n_addr = normalize_building_address(p_addr)
        if n_name and n_addr:
            return BuildingMaster.objects.filter(normalized_name=n_name, normalized_address=n_addr).first()
    except Exception:
        pass
    return None

def _extract_bm_seismic_and_elevator(bm_obj, combined_text):
    eq_res = getattr(bm_obj, 'earthquake_resistance', '') or ''
    if "免震" in str(eq_res):
        seismic = 1.0
    elif "制震" in str(eq_res):
        seismic = 0.5
    else:
        seismic = 0.0

    ev_avail = getattr(bm_obj, 'elevator_available', None) if bm_obj else None
    if ev_avail is True:
        has_ev = 1.0
    elif ev_avail is False:
        has_ev = -1.0
    else:
        has_ev = 1.0 if re.search(r'エレベーター|EV', combined_text) else 0.0
    return seismic, has_ev

def _extract_land_rent_features(property_obj, combined_text):
    raw_chidai = _get_attr(property_obj, 'chidai', None)
    if raw_chidai is None:
        raw_chidai_str = _get_attr(property_obj, 'chidaiStr', '')
        if raw_chidai_str:
            raw_chidai = converter.parse_chidai(raw_chidai_str)
    if raw_chidai is None and re.search(r'借地権|地上権|賃借権', combined_text):
        rent_match = re.search(r'((?:地代|借地料)[^\d\r\n]{0,15}\d[\d,]*(?:\.\d+)?\s*万?円(?:\s*/\s*[年月])?)', combined_text)
        if rent_match:
            raw_chidai = converter.parse_chidai(rent_match.group(1))

    monthly_land_rent = (float(raw_chidai) / 10000.0) if raw_chidai and float(raw_chidai) > 0 else 0.0
    annual_land_rent = monthly_land_rent * 12.0
    land_rent_liability = annual_land_rent / 0.05 if annual_land_rent > 0 else 0.0
    raw_p = _get_attr(property_obj, 'price', 0)
    price_man_val = (float(raw_p) / 10000.0) if raw_p and float(raw_p) > 100000 else float(raw_p or 0.0)
    land_rent_ratio = (annual_land_rent / price_man_val) if price_man_val > 0 else 0.0
    return monthly_land_rent, annual_land_rent, land_rent_liability, land_rent_ratio

def _extract_building_master_and_amenity_features(property_obj, combined_text):
    bm_obj = _resolve_building_master_obj(property_obj)
    dev_tier = getattr(bm_obj, 'developer_tier', 'unknown') if bm_obj else 'unknown'
    dev_scores = {"major_reputable": 1.0, "standard": 0.5}
    contractor_tier = getattr(bm_obj, 'contractor_tier', 'unknown') if bm_obj else 'unknown'
    cont_scores = {"super_general": 1.0, "major": 0.6}

    seismic, has_ev = _extract_bm_seismic_and_elevator(bm_obj, combined_text)
    hallway = getattr(bm_obj, 'hallway_type', '') or ''
    is_indoor = 1.0 if "内廊下" in str(hallway) or "内廊下" in combined_text else 0.0
    gb = getattr(bm_obj, 'garbage_disposal_24h', None) if bm_obj else None
    has_gb = 1.0 if gb or "24時間ゴミ出し" in combined_text or "ゴミステーション" in combined_text else 0.0

    (
        monthly_land_rent, annual_land_rent, land_rent_liability, land_rent_ratio
    ) = _extract_land_rent_features(property_obj, combined_text)

    return {
        "bm_brand_tier_score": dev_scores.get(dev_tier, 0.0),
        "bm_contractor_tier_score": cont_scores.get(contractor_tier, 0.0),
        "bm_is_seismic_isolated": seismic,
        "bm_has_elevator": has_ev,
        "bm_is_indoor_hallway": is_indoor,
        "bm_has_24h_garbage": has_gb,
        "has_disposer": 1.0 if re.search(r'ディスポーザー', combined_text) else 0.0,
        "is_corner_unit": 1.0 if re.search(r'角部屋|角住戸', combined_text) else 0.0,
        "is_leasehold": 1.0 if re.search(r'借地権|地上権|賃借権', combined_text) else 0.0,
        "has_psychological_defect": 1.0 if re.search(r'告知事項|心理的瑕疵', combined_text) else 0.0,
        "monthly_land_rent": monthly_land_rent,
        "annual_land_rent": annual_land_rent,
        "land_rent_liability": land_rent_liability,
        "land_rent_ratio": land_rent_ratio,
        "visual_adjustment_percent": safe_float(_get_attr(property_obj, 'visual_adjustment_percent', 0.0), 0.0)
    }

def _calculate_digest_volume_features(property_type, tochi_area, tatemono_area, max_youseki):
    if property_type not in ['kodate', 'apartment'] or tochi_area <= 0:
        return 0.0, 0.0, 0
    digest_volume_ratio = (tatemono_area / tochi_area) * 100.0
    surplus_volume_potential = max(0.0, max_youseki - digest_volume_ratio)
    non_conforming_flag = 1 if digest_volume_ratio > max_youseki else 0
    return digest_volume_ratio, surplus_volume_potential, non_conforming_flag

def _calculate_shin_taishin(property_obj, chikunen):
    chikunengetsu = _get_raw_chikunengetsu(property_obj)
    if chikunengetsu and isinstance(chikunengetsu, datetime.date):
        return 0 if chikunengetsu < datetime.date(1981, 6, 1) else 1
    return 0 if chikunen > 45.0 else 1

def _calculate_hazard_features(address1, address2):
    hz = _hazard_cache.get((address1, address2))
    if hz:
        return int(hz.flood_risk_level), int(hz.landslide_risk_level)
    return 0, 0

def _calculate_effective_building_and_floor_area(property_obj, tochi_area, max_kenpei, actual_volume_limit):
    road_struct = _get_attr(property_obj, 'roadStructure', '') or _get_attr(property_obj, 'setsudou', '') or ''
    is_corner = any(x in str(road_struct) for x in ("角地", "準角地", "三方", "四方"))
    effective_kenpei = min(100.0, max_kenpei + 10.0) if is_corner else max_kenpei
    max_building_area = tochi_area * (effective_kenpei / 100.0) if tochi_area > 0 else 0.0
    max_floor_area = tochi_area * (actual_volume_limit / 100.0) if tochi_area > 0 else 0.0
    return max_building_area, max_floor_area

def _calculate_kanri_and_lifespan(property_obj, chikunen):
    raw_kanri = float(_get_attr(property_obj, 'kanrihi', 0) or 0)
    kanrihi = int(min(raw_kanri / 10000.0, 30000.0) if raw_kanri > 200000.0 else raw_kanri)
    raw_syuzen = float(_get_attr(property_obj, 'syuzenTsumitate', 0) or 0)
    syuzen = int(min(raw_syuzen / 10000.0, 30000.0) if raw_syuzen > 200000.0 else raw_syuzen)
    kouzou_str = _get_attr(property_obj, 'kouzou', '') or _get_attr(property_obj, 'structure', '') or ''
    kouzou_cat = parse_kouzou(kouzou_str)
    lifespan_val = LIFESPAN.get(kouzou_cat, 30)
    kouzou_lifespan_ratio = min(2.5, float(chikunen) / float(lifespan_val)) if lifespan_val > 0 else 1.0
    return kanrihi, syuzen, kouzou_str, kouzou_lifespan_ratio

def build_features(property_obj, property_type, base_date=None, mkt_comparison_master=None):
    """
    共通特徴量エンジニアリング関数 (Djangoモデルオブジェクトまたは辞書に対応)
    """
    address1, address2, station1, company = _extract_clean_address(property_obj)
    eval_base_date, ref_prop_date, time_diff_months, is_legacy = _resolve_eval_dates_and_diff(property_obj, base_date)
    macro_repi, jgb, nikkei, reit, const_cost = _extract_macro_features(ref_prop_date, property_type)
    chikunen = _calculate_chikunen_feature(property_obj, property_type, eval_base_date)
    walk_min, bus_min, bus_walk, bus_use = _extract_traffic_and_walk_min(property_obj)
    area, tatemono_area, tochi_area, setback_ratio_temp = _calculate_area_and_setback(property_obj, property_type)

    _init_global_caches()
    pop_growth, income, total_population, income_growth_rate, pop_density = _query_municipal_potential(address1, address2)
    passenger_volume = _query_station_volume(station1)
    effective_walk_min = _calculate_effective_walk_min(walk_min, bus_use, bus_min, bus_walk, pop_density)
    max_youseki, max_kenpei, zone_max_kenpei, zone_max_youseki, zone_name_prop = _resolve_zone_limits(property_obj)
    average_land_price, estimated_rosenka_price, estimated_fixed_asset_price, land_price_growth_rate = _blend_land_prices(address1, address2, max_youseki)

    digest_volume_ratio, surplus_volume_potential, non_conforming_flag = _calculate_digest_volume_features(
        property_type, tochi_area, tatemono_area, max_youseki
    )

    (
        potential_floor_area, scale_discount, cost_approach_value,
        mkt_comparison_value, income_approach_value, gross_yield, annual_rent
    ) = _calculate_appraisal_values(
        property_obj, property_type, area, tatemono_area, tochi_area,
        chikunen, max_youseki, average_land_price, income, mkt_comparison_master,
        address1, address2
    )

    is_shin_taishin = _calculate_shin_taishin(property_obj, chikunen)
    flood_risk_level, landslide_risk_level = _calculate_hazard_features(address1, address2)

    (
        maguchi_val, road_width_val, setback_ratio, actual_volume_limit,
        volume_digest_factor, road_condition_factor, frontage_penalty_factor,
        residual_land_value, road_direction_str, road_type_str, road_structure_str, chimoku_str
    ) = _calculate_tochi_appraisal_factors(
        property_obj, property_type, tochi_area, max_youseki, average_land_price, setback_ratio_temp
    )
    if property_type == 'tochi':
        area = tochi_area

    max_building_area, max_floor_area = _calculate_effective_building_and_floor_area(
        property_obj, tochi_area, max_kenpei, actual_volume_limit
    )

    shape_feats, cost_approach_value, mkt_comparison_value, residual_land_value = _calculate_plot_shape_features(
        property_obj, property_type, cost_approach_value, mkt_comparison_value, residual_land_value
    )

    combined_text = _extract_combined_text_for_prop(property_obj)
    legal_furuya_feats = _extract_legal_and_furuya_features(
        property_type, combined_text, chikunen, tochi_area, tatemono_area,
        average_land_price, scale_discount, cost_approach_value, income_approach_value, residual_land_value
    )
    bm_amenity_feats = _extract_building_master_and_amenity_features(property_obj, combined_text)

    kanrihi, syuzen, kouzou_str, kouzou_lifespan_ratio = _calculate_kanri_and_lifespan(property_obj, chikunen)

    feats = {
        "area": area if property_type in ['mansion', 'tochi'] else tatemono_area,
        "tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "walk_min": walk_min,
        "kanrihi": kanrihi,
        "syuzen": syuzen,
        "pop_growth": pop_growth,
        "income": income,
        "passenger_volume": passenger_volume,
        "average_land_price": average_land_price,
        "estimated_rosenka_price": estimated_rosenka_price,
        "estimated_fixed_asset_price": estimated_fixed_asset_price,
        "cost_approach_value": cost_approach_value,
        "mkt_comparison_value": mkt_comparison_value,
        "income_approach_value": income_approach_value,
        "residual_land_value": residual_land_value,
        "digest_volume_ratio": digest_volume_ratio,
        "surplus_volume_potential": surplus_volume_potential,
        "non_conforming_flag": non_conforming_flag,
        "gross_yield": float(gross_yield) if gross_yield else 0.0,
        "annual_rent": float(annual_rent) if annual_rent else 0.0,
        "is_shin_taishin": is_shin_taishin,
        "flood_risk_level": flood_risk_level,
        "landslide_risk_level": landslide_risk_level,
        "max_youseki": max_youseki,
        "max_kenpei": max_kenpei,
        "maguchi": maguchi_val,
        "road_width": road_width_val,
        "setback_ratio": setback_ratio,
        "actual_volume_limit": actual_volume_limit,
        "volume_digest_factor": volume_digest_factor,
        "road_condition_factor": road_condition_factor,
        "frontage_penalty_factor": frontage_penalty_factor,
        "max_building_area": max_building_area,
        "max_floor_area": max_floor_area,
        "total_population": total_population,
        "income_growth_rate": income_growth_rate,
        "land_price_growth_rate": land_price_growth_rate,
        "effective_walk_min": effective_walk_min,
        "population_density": pop_density,
        "potential_floor_area": potential_floor_area,
        "scale_discount": scale_discount,
        "zone_max_kenpei": zone_max_kenpei,
        "zone_max_youseki": zone_max_youseki,
        "kouzou_lifespan_ratio": kouzou_lifespan_ratio,
        "prefecture": address1,
        "city": address2,
        "station": station1,
        "company": company,
        "kouzou": kouzou_str,
        "road_direction": road_direction_str,
        "road_type": road_type_str,
        "road_structure": road_structure_str,
        "chimoku": chimoku_str,
        "time_diff_months": time_diff_months,
        "macro_repi": macro_repi,
        "macro_jgb_10y": jgb,
        "macro_nikkei": nikkei,
        "macro_reit": reit,
        "macro_construction_cost": const_cost,
        "is_legacy_data": is_legacy,
        "interior_score": safe_float(_get_attr(property_obj, 'interior_score', 0.0), 0.0),
        "layout_score": safe_float(_get_attr(property_obj, 'layout_score', 0.0), 0.0),
    }

    feats.update(shape_feats)
    feats.update(legal_furuya_feats)
    feats.update(bm_amenity_feats)

    feats.update(parse_road_direction_features(road_direction_str))
    feats.update(parse_road_type_features(road_type_str))
    feats.update(parse_road_structure_features(road_structure_str))
    feats.update(parse_chimoku_features(chimoku_str))
    feats.update(parse_kouzou_features(kouzou_str))
    feats.update(parse_company_features(company))
    youto_val = _get_attr(property_obj, 'youtoChiiki', '') or str(zone_name_prop or '')
    feats.update(parse_youto_zone_features(youto_val))
    madori_val = _get_attr(property_obj, 'madori', '') or _get_attr(property_obj, 'roomLayout', '') or ''
    feats.update(parse_madori_layout_features(madori_val, combined_text))
    floor_val = _get_attr(property_obj, 'kai', '') or _get_attr(property_obj, 'floor', '') or _get_attr(property_obj, 'floorNumber', '') or _get_attr(property_obj, 'kaisu', '') or ''
    total_floor_val = _get_attr(property_obj, 'chijo', '') or _get_attr(property_obj, 'totalFloor', '') or _get_attr(property_obj, 'totalFloors', '') or ''
    feats.update(parse_floor_features(floor_val, total_floor_val, combined_text))

    return feats



def build_features_batch(properties_list, property_type, base_date=None, mkt_comparison_master=None):
    """
    複数物件リストに対して一括で特徴量辞書リストを生成する高パフォーマンスヘルパー
    """
    _init_global_caches()
    results = []
    for prop in properties_list:
        try:
            feats = build_features(prop, property_type, base_date=base_date, mkt_comparison_master=mkt_comparison_master)
            results.append(feats)
        except Exception:
            # 万一の個別パース例外時は空辞書でなくデフォルト値でフォールバック
            fallback = dict.fromkeys(FEATURE_SETS.get(property_type, {}).get("first", []), 0.0)
            fallback["area"] = 50.0
            results.append(fallback)
    return results

