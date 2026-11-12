"""
Feature Builder for Real Estate ML Pipeline.
Orchestrates domain-specific feature extraction submodules.
"""

import logging
import math

from .appraisal import (
    _calculate_appraisal_values,
    _calculate_tochi_appraisal_factors,
    detect_road_missingness,
)
from .building import (
    _calculate_kanri_and_lifespan,
    _extract_building_master_and_amenity_features,
    _prefetch_building_masters,
)
from .bias_correction import calculate_bias_correction_features
from .feature_sets import FEATURE_SETS
from .land_valuation_extras import LandValuationContext, extract_land_valuation_extras
from .legal_furuya import (
    _extract_combined_text_for_prop,
    _extract_legal_and_furuya_features,
)
from .parsers import (
    _calculate_area_and_setback,
    _calculate_chikunen_feature,
    _calculate_digest_volume_features,
    _calculate_effective_building_and_floor_area,
    _calculate_shin_taishin,
    _extract_clean_address,
    _extract_group_labels,
    _extract_traffic_and_walk_min,
    _get_attr,
    _resolve_eval_dates_and_diff,
    parse_chimoku_features,
    parse_company_features,
    parse_floor_features,
    parse_kouzou_features,
    parse_land_specific_features,
    parse_madori_layout_features,
    parse_road_direction_features,
    parse_road_structure_features,
    parse_road_type_features,
    parse_youto_zone_features,
    safe_float,
)
from .plot_shape import _calculate_plot_shape_features
from .reference_data import (
    _blend_land_prices,
    _calculate_effective_walk_min,
    _calculate_regional_sensitivity_features,
    _extract_macro_features,
    _init_global_caches,
    _query_extended_hazard_features,
    _query_hierarchy_centroid,
    _query_micro_land_price_features,
    _query_municipal_potential,
    _query_station_volume,
    _query_future_population_features,
    _query_urban_induction_zone_features,
    _query_historical_momentum_features,
    _resolve_zone_limits,
)
from package.utils.gsi_geocoder import lookup_cached_coordinates

logger = logging.getLogger(__name__)


def _first_valid_attr(obj, *names, default=''):
    for name in names:
        val = _get_attr(obj, name, None)
        if val:
            return val
    return default


def _resolve_property_coordinates(
    property_obj, chome_group: str, address1: str = '', address2: str = '', station1: str = ''
) -> tuple[float | None, float | None]:
    lat_val = safe_float(_first_valid_attr(property_obj, 'latitude', 'lat', default=None), None)
    lon_val = safe_float(_first_valid_attr(property_obj, 'longitude', 'lon', 'lng', default=None), None)
    if lat_val is not None and lon_val is not None:
        return float(lat_val), float(lon_val)
    for query_str in (str(_get_attr(property_obj, 'address', '') or ''), chome_group):
        if query_str:
            hit = lookup_cached_coordinates(query_str)
            if hit is not None:
                return hit
    return _query_hierarchy_centroid(address1, address2, chome_group, station1)


def _resolve_gross_tochi_area(property_obj, property_type: str, effective_tochi_area: float) -> float:
    if property_type == 'mansion':
        return 0.0
    raw = safe_float(_get_attr(property_obj, 'tochiMenseki', None), 0.0)
    if raw <= 0.0 and property_type == 'tochi':
        raw = safe_float(_get_attr(property_obj, 'area', None), 0.0)
    return raw if raw > 0.0 else effective_tochi_area


def _extract_category_feature_updates(property_obj, combined_text, zone_name_prop) -> dict:
    updates = {}
    youto_val = _first_valid_attr(property_obj, 'youtoChiiki', default=str(zone_name_prop or ''))
    updates.update(parse_youto_zone_features(youto_val))
    madori_val = _first_valid_attr(property_obj, 'madori', 'roomLayout')
    updates.update(parse_madori_layout_features(madori_val, combined_text))
    floor_val = _first_valid_attr(property_obj, 'kai', 'floor', 'floorNumber', 'kaisu')
    total_floor_val = _first_valid_attr(property_obj, 'chijo', 'totalFloor', 'totalFloors')
    updates.update(parse_floor_features(floor_val, total_floor_val, combined_text))
    return updates


def build_features(property_obj, property_type, base_date=None, mkt_comparison_master=None, building_master_lookup=None):
    """
    共通特徴量エンジニアリング関数 (Djangoモデルオブジェクトまたは辞書に対応)
    building_master_lookup: build_features_batch が一括取得した建物マスタ（None なら物件単位で解決）
    """
    _init_global_caches()
    address1, address2, station1, company = _extract_clean_address(property_obj)
    building_group, chome_group = _extract_group_labels(property_obj, address1, address2)
    eval_base_date, ref_prop_date, time_diff_months, is_legacy = _resolve_eval_dates_and_diff(property_obj, base_date)
    macro_repi, jgb, nikkei, reit, const_cost = _extract_macro_features(ref_prop_date, property_type)
    chikunen, is_chikunen_unknown = _calculate_chikunen_feature(property_obj, property_type, eval_base_date)
    walk_min, bus_min, bus_walk, bus_use = _extract_traffic_and_walk_min(property_obj)
    area, tatemono_area, tochi_area, setback_ratio_temp = _calculate_area_and_setback(property_obj, property_type)
    gross_tochi_area = _resolve_gross_tochi_area(property_obj, property_type, tochi_area)
    if property_type == 'tochi':
        area = gross_tochi_area

    pop_growth, income, total_population, income_growth_rate, pop_density = _query_municipal_potential(address1, address2)
    passenger_volume = _query_station_volume(station1)
    future_pop_change_2035, working_age_ratio_2035, elderly_ratio_2035, single_ratio_2035 = _query_future_population_features(address1, address2)
    is_urban_induction, is_residential_induction = _query_urban_induction_zone_features(address1, address2)
    st_vol_cagr, muni_inc_cagr, muni_pop_mom = _query_historical_momentum_features(address1, address2, station1, ref_prop_date.year if ref_prop_date else 2024)
    effective_walk_min = _calculate_effective_walk_min(walk_min, bus_use, bus_min, bus_walk, pop_density)
    lat_val, lon_val = _resolve_property_coordinates(property_obj, chome_group, address1, address2, station1)
    max_youseki, max_kenpei, zone_max_kenpei, zone_max_youseki, zone_name_prop = _resolve_zone_limits(
        property_obj,
        prefecture=address1,
        city=address2,
        chome_group=chome_group,
        latitude=lat_val,
        longitude=lon_val,
    )
    average_land_price, estimated_rosenka_price, estimated_fixed_asset_price, land_price_growth_rate = _blend_land_prices(address1, address2, max_youseki)
    micro_land_price, chome_infra_score = _query_micro_land_price_features(
        address1, address2, chome_group, max_youseki, average_land_price,
        station_name=station1, latitude=lat_val, longitude=lon_val,
    )

    digest_volume_ratio, surplus_volume_potential, non_conforming_flag = _calculate_digest_volume_features(
        property_type, tochi_area, tatemono_area, max_youseki
    )

    (
        potential_floor_area, scale_discount, cost_approach_value,
        mkt_comparison_value, income_approach_value, gross_yield, annual_rent
    ) = _calculate_appraisal_values(
        property_obj, property_type, area, tatemono_area, tochi_area,
        chikunen, max_youseki, micro_land_price, income, mkt_comparison_master,
        address1, address2
    )

    is_shin_taishin = _calculate_shin_taishin(property_obj, chikunen)
    (
        flood_risk_level,
        landslide_risk_level,
        tsunami_risk_level,
        red_zone_landslide_flag,
        liquefaction_risk_level,
    ) = _query_extended_hazard_features(address1, address2)

    (
        maguchi_val, road_width_val, setback_ratio, actual_volume_limit,
        volume_digest_factor, road_condition_factor, frontage_penalty_factor,
        residual_land_value, road_direction_str, road_type_str, road_structure_str, chimoku_str
    ) = _calculate_tochi_appraisal_factors(
        property_obj, property_type, tochi_area, max_youseki, micro_land_price, setback_ratio_temp, scale_discount
    )
    is_maguchi_missing, is_road_width_missing = (
        (0.0, 0.0) if property_type == 'mansion' else detect_road_missingness(property_obj)
    )
    if property_type == 'tochi':
        area = gross_tochi_area

    max_building_area, max_floor_area = _calculate_effective_building_and_floor_area(
        property_obj, tochi_area, max_kenpei, actual_volume_limit
    )

    shape_feats, cost_approach_value, mkt_comparison_value, residual_land_value = _calculate_plot_shape_features(
        property_obj, property_type, cost_approach_value, mkt_comparison_value, residual_land_value
    )

    combined_text = _extract_combined_text_for_prop(property_obj)
    legal_furuya_feats = _extract_legal_and_furuya_features(
        property_type, combined_text, chikunen, tochi_area, tatemono_area,
        micro_land_price, scale_discount, cost_approach_value, income_approach_value, residual_land_value,
        property_obj=property_obj,
        estimated_fixed_asset_price=float(estimated_fixed_asset_price),
    )
    bm_amenity_feats = _extract_building_master_and_amenity_features(property_obj, combined_text, building_master_lookup)

    kanrihi, syuzen, kouzou_str, kouzou_lifespan_ratio = _calculate_kanri_and_lifespan(property_obj, chikunen)

    (
        walk_min_elasticity, effective_station_dist,
        chikunen_resistance, area_intensity
    ) = _calculate_regional_sensitivity_features(
        property_type, walk_min, pop_density, passenger_volume, micro_land_price,
        area, tatemono_area, tochi_area, chikunen, scale_discount
    )

    bias_feats = calculate_bias_correction_features(
        property_obj, property_type, chikunen, tatemono_area,
        micro_land_price, kouzou_str, combined_text, legal_furuya_feats.get("is_shigaika_chousei", 0.0)
    )

    target_area = area if property_type in ('mansion', 'tochi') else tatemono_area
    narrow_penalty = 0.80 if (float(road_width_val) > 0 and float(road_width_val) < 4.0) or float(setback_ratio) > 0 else 1.0

    feats = {
        "area": target_area,
        "tochi_menseki": tochi_area,
        "effective_tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "is_chikunen_unknown": is_chikunen_unknown,
        "walk_min": walk_min,
        "kanrihi": kanrihi,
        "syuzen": syuzen,
        "pop_growth": pop_growth if pop_growth is not None else 0.0,
        "income": income if income is not None else 0.0,
        "passenger_volume": passenger_volume if passenger_volume is not None else 0.0,
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
        "tsunami_risk_level": tsunami_risk_level,
        "red_zone_landslide_flag": red_zone_landslide_flag,
        "liquefaction_risk_level": liquefaction_risk_level,
        "latitude": float(lat_val) if lat_val is not None else 0.0,
        "longitude": float(lon_val) if lon_val is not None else 0.0,
        "building_oof_unit_price": 0.0,
        "knn_500m_oof_unit_price": 0.0,
        "knn_500m_comp_count": 0.0,
        "max_youseki": max_youseki,
        "max_kenpei": max_kenpei,
        "maguchi": maguchi_val,
        "road_width": road_width_val,
        "is_maguchi_missing": is_maguchi_missing,
        "is_road_width_missing": is_road_width_missing,
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
        "log_tochi_menseki": round(math.log(max(1.0, float(tochi_area))), 4),
        "narrow_road_penalty": narrow_penalty,
        "building_depreciation_ratio": bias_feats["building_depreciation_ratio"],
        "demolition_cost_discount": bias_feats["demolition_cost_discount"],
        "mansion_vintage_floor": bias_feats["mansion_vintage_floor"],
        "scale_vintage_interaction": bias_feats["scale_vintage_interaction"],
        "low_demand_land_discount": bias_feats["low_demand_land_discount"],
        "zone_max_kenpei": zone_max_kenpei,
        "zone_max_youseki": zone_max_youseki,
        "kouzou_lifespan_ratio": kouzou_lifespan_ratio,
        "walk_min_elasticity": walk_min_elasticity,
        "effective_station_distance": effective_station_dist,
        "chikunen_depreciation_resistance": chikunen_resistance,
        "area_value_intensity": area_intensity,
        "prefecture": address1,
        "city": address2,
        "station": station1,
        "company": company,
        "building_group": building_group,
        "chome_group": chome_group,
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
        "future_pop_change_2035": future_pop_change_2035,
        "future_working_age_ratio_2035": working_age_ratio_2035,
        "future_elderly_ratio_2035": elderly_ratio_2035,
        "future_single_household_ratio_2035": single_ratio_2035,
        "is_in_urban_induction_zone": is_urban_induction,
        "is_in_residential_induction_zone": is_residential_induction,
        "station_volume_3y_cagr": st_vol_cagr,
        "municipal_income_3y_cagr": muni_inc_cagr,
        "municipal_pop_momentum": muni_pop_mom,
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
    feats.update(parse_land_specific_features(property_obj, combined_text))
    feats.update(_extract_category_feature_updates(property_obj, combined_text, zone_name_prop))
    feats.update(
        extract_land_valuation_extras(
            LandValuationContext(
                property_obj=property_obj,
                property_type=property_type,
                combined_text=combined_text,
                gross_area=target_area,
                effective_tochi_area=tochi_area,
                tatemono_area=tatemono_area,
                chikunen=chikunen,
                micro_land_price=micro_land_price,
                average_land_price=average_land_price,
                chome_infra_score=chome_infra_score,
                maguchi_val=maguchi_val,
                road_width_val=road_width_val,
                scale_discount=scale_discount,
                road_condition_factor=road_condition_factor,
                frontage_penalty_factor=frontage_penalty_factor,
                plot_shape_penalty=float(feats.get("plot_shape_penalty", 1.0)),
                rights_ratio=float(feats.get("rights_ratio", 1.0)),
                is_saikenchiku_fuka=float(feats.get("is_saikenchiku_fuka", 0.0)),
                is_shigaika_chousei=float(feats.get("is_shigaika_chousei", 0.0)),
                effective_land_price_multiplier=float(feats.get("effective_land_price_multiplier", 1.0)),
                furuya_demolition_cost=float(feats.get("furuya_demolition_cost", 0.0)),
                cost_approach_value=float(feats["cost_approach_value"]),
                income_approach_value=float(feats["income_approach_value"]),
                mkt_comparison_master=mkt_comparison_master,
                address1=address1,
                address2=address2,
                chome_group=chome_group,
                latitude=lat_val,
                longitude=lon_val,
                mkt_comparison_value=float(feats["mkt_comparison_value"]),
                building_depreciation_ratio=float(feats["building_depreciation_ratio"]),
                demolition_cost_discount=float(feats["demolition_cost_discount"]),
            )
        )
    )

    return feats


def build_features_batch(properties_list, property_type, base_date=None, mkt_comparison_master=None):
    """
    複数物件リストに対して一括で特徴量辞書リストを生成する高パフォーマンスヘルパー
    （参照マスタは1回だけロードし、建物マスタは一括取得する）
    """
    _init_global_caches()
    bm_lookup = _prefetch_building_masters(properties_list)
    results = []
    for prop in properties_list:
        try:
            feats = build_features(prop, property_type, base_date=base_date, mkt_comparison_master=mkt_comparison_master,
                                   building_master_lookup=bm_lookup)
            results.append(feats)
        except Exception:
            logger.warning("ML: build_features failed for %s (%s); using fallback features",
                           _get_attr(prop, 'pageUrl', None) or _get_attr(prop, 'address', ''), property_type, exc_info=True)
            fallback = dict.fromkeys(FEATURE_SETS.get(property_type, {}).get("first", []), 0.0)
            fallback["area"] = 50.0
            results.append(fallback)
    return results
