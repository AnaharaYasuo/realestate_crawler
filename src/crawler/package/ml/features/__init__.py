"""
ML 特徴量エンジニアリング パッケージ (Issue #713, Epic #710)

features.py (2,000行) を責務別サブモジュールに分割し、
従来の `from package.ml.features import ...` に対する完全な後方互換性を提供します。
"""

# 定数および特徴量セット
# 不動産鑑定評価
from .appraisal import (
    AppraisalValues,
    TochiAppraisalFactors,
    _calculate_appraisal_values,
    _calculate_road_factors,
    _calculate_tochi_appraisal_factors,
    _extract_road_specs,
    _fallback_road_classification,
    _fallback_road_dimensions,
    _resolve_cap_rate,
    calculate_appraisal_values,
    calculate_income_approach_value,
    calculate_mkt_comparison_value,
    calculate_tochi_appraisal_factors,
)

# メインビルダー
from .builder import (
    build_features,
    build_features_batch,
)

# 建物マスタ・設備・地代
from .building import (
    _calculate_kanri_and_lifespan,
    _extract_bm_seismic_and_elevator,
    _extract_building_master_and_amenity_features,
    _extract_land_rent_features,
    _prefetch_building_masters,
    _resolve_building_master_obj,
    building_master_key,
    calculate_kanri_and_lifespan,
    extract_building_master_and_amenity_features,
    extract_land_rent_features,
    prefetch_building_masters,
    resolve_building_master_obj,
)
from .constants import LIFESPAN, PREFECTURE_BASE_LAND_PRICES, REPLACEMENT_COSTS
from .feature_sets import FEATURE_SETS

# 法令・古家・権利割合
from .legal_furuya import (
    _adjust_tochi_furuya_values,
    _calculate_furuya_values,
    _determine_demolish_unit,
    _evaluate_furuya,
    _extract_combined_text_for_prop,
    _extract_legal_and_furuya_features,
    evaluate_furuya,
    extract_combined_text_for_prop,
    extract_legal_and_furuya_features,
)

# 属性パーサーおよび基本変換
from .parsers import (
    _calculate_area_and_setback,
    _calculate_chikunen_feature,
    _calculate_desk_setback,
    _calculate_digest_volume_features,
    _calculate_effective_building_and_floor_area,
    _calculate_shin_taishin,
    _check_is_legacy,
    _clean_addr2,
    _collect_setback_candidate_texts,
    _extract_clean_address,
    _extract_floor_number,
    _extract_setback_from_text,
    _extract_total_floors,
    _extract_traffic_and_walk_min,
    _fallback_address,
    _get_attr,
    _get_raw_chikunengetsu,
    _parse_date_value,
    _parse_float_from_str,
    _parse_seireki_date,
    _parse_setback_area,
    _parse_wareki_date,
    _resolve_eval_base_date,
    _resolve_eval_dates_and_diff,
    calculate_chikunen,
    parse_chimoku_features,
    parse_company_features,
    parse_floor_features,
    parse_kouzou,
    parse_kouzou_features,
    parse_madori_layout_features,
    parse_road_direction_features,
    parse_road_structure_features,
    parse_road_type_features,
    parse_youto_zone_features,
    safe_float,
)

# 敷地形状
from .plot_shape import (
    _apply_plot_shape_discount,
    _build_fallback_shape_features,
    _build_shape_metrics_features,
    _calculate_plot_shape_features,
    _resolve_kagechi_ratio,
    calculate_plot_shape_features,
)

# 参照マスタおよびキャッシュ管理
from .reference_data import (
    _all_caches_populated,
    _blend_land_prices,
    _calculate_commercial_weight,
    _calculate_effective_walk_min,
    _calculate_hazard_features,
    _clear_all_caches,
    _extract_limit_by_regex,
    _extract_macro_features,
    _extract_slash_limit,
    _fallback_zone_from_keywords,
    _fill_if_empty,
    _find_first_attr,
    _find_zone_record_by_keywords,
    _find_zone_record_by_name,
    _get_land_price_stats,
    _get_macro_record,
    _get_nationwide_base_land_price,
    _init_global_caches,
    _init_lp_cache,
    _init_misc_caches,
    _init_muni_cache,
    _load_all_potential_caches_once,
    _match_regional_hub_price,
    _match_tokyo_district_price,
    _pick_macro_repi,
    _query_municipal_potential,
    _query_station_volume,
    _resolve_zone_from_record,
    _resolve_zone_limits,
    blend_land_prices,
    extract_limit_value,
    extract_macro_features,
    query_hazard_features,
    query_municipal_potential,
    query_station_volume,
    reset_reference_caches,
    resolve_zone_limits,
)

__all__ = [
    "FEATURE_SETS",
    "LIFESPAN",
    "PREFECTURE_BASE_LAND_PRICES",
    "REPLACEMENT_COSTS",
    "AppraisalValues",
    "TochiAppraisalFactors",
    "_clear_all_caches",
    "_hazard_cache",
    "_init_global_caches",
    "_load_all_potential_caches_once",
    "_lp_cache",
    "_lp_pref_comm_cache",
    "_lp_pref_res_cache",
    "_macro_cache",
    "_muni_cache",
    "_muni_pref_cache",
    "_station_cache",
    "_zone_cache",
    "build_features",
    "build_features_batch",
    "calculate_chikunen",
    "parse_chimoku_features",
    "parse_company_features",
    "parse_floor_features",
    "parse_kouzou",
    "parse_kouzou_features",
    "parse_madori_layout_features",
    "parse_road_direction_features",
    "parse_road_structure_features",
    "parse_road_type_features",
    "parse_youto_zone_features",
    "reset_reference_caches",
    "safe_float",
]


import sys
import types

from . import reference_data as _ref_mod

_CACHE_ATTRS = {
    "_muni_cache",
    "_muni_pref_cache",
    "_station_cache",
    "_lp_cache",
    "_lp_pref_res_cache",
    "_lp_pref_comm_cache",
    "_hazard_cache",
    "_zone_cache",
    "_macro_cache",
}


class _FeaturesModule(types.ModuleType):
    def __getattr__(self, name: str):
        if name in _CACHE_ATTRS:
            return getattr(_ref_mod, name)
        return super().__getattr__(name)

    def __setattr__(self, name: str, value):
        if name in _CACHE_ATTRS:
            setattr(_ref_mod, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _FeaturesModule
