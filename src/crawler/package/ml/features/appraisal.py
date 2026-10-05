"""
ML 不動産鑑定評価額（原価法・取引事例比較法・収益還元法・接道補正・残余地価）モジュール (Issue #713, Epic #710)
"""
import re
from dataclasses import dataclass
from typing import Any

from package.ml.features.constants import LIFESPAN, REPLACEMENT_COSTS
from package.ml.features.parsers import parse_kouzou, safe_float


@dataclass(slots=True, frozen=True)
class AppraisalValues:
    potential_floor_area: float
    scale_discount: float
    cost_approach_value: float
    mkt_comparison_value: float
    income_approach_value: float
    gross_yield: Any
    annual_rent: Any

    def __iter__(self):
        yield self.potential_floor_area
        yield self.scale_discount
        yield self.cost_approach_value
        yield self.mkt_comparison_value
        yield self.income_approach_value
        yield self.gross_yield
        yield self.annual_rent


@dataclass(slots=True, frozen=True)
class TochiAppraisalFactors:
    maguchi_val: float
    road_width_val: float
    setback_ratio: float
    actual_volume_limit: float
    volume_digest_factor: float
    road_condition_factor: float
    frontage_penalty_factor: float
    residual_land_value: float
    road_direction_str: str
    road_type_str: str
    road_structure_str: str
    chimoku_str: str

    def __iter__(self):
        yield self.maguchi_val
        yield self.road_width_val
        yield self.setback_ratio
        yield self.actual_volume_limit
        yield self.volume_digest_factor
        yield self.road_condition_factor
        yield self.frontage_penalty_factor
        yield self.residual_land_value
        yield self.road_direction_str
        yield self.road_type_str
        yield self.road_structure_str
        yield self.chimoku_str


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _find_first_attr(property_obj: Any, attrs: tuple[str, ...]) -> Any:
    for a in attrs:
        val = _get_attr(property_obj, a, None)
        if val is not None:
            return val
    return None


def calculate_mkt_comparison_value(
    mkt_comparison_master: dict | None,
    address1: str,
    address2: str,
    property_type: str,
    chikunen: float,
    eval_area: float,
    average_land_price: float
) -> float:
    if not mkt_comparison_master:
        return eval_area * (average_land_price / 10000.0)
    age_band = int(chikunen // 10)
    key = (address1, address2, property_type, age_band)
    avg_unit_price = mkt_comparison_master.get(key)
    if avg_unit_price is None:
        keys_pref = [k for k in mkt_comparison_master if k[0] == address1 and k[2] == property_type and k[3] == age_band]
        avg_unit_price = (sum(mkt_comparison_master[k] for k in keys_pref) / len(keys_pref)) if keys_pref else 30.0
    return avg_unit_price * eval_area


def _resolve_cap_rate(gross_yield: Any, income: float) -> float:
    if gross_yield is not None and float(gross_yield) > 0:
        return float(gross_yield) / 100.0
    if income > 7000:
        return 0.040
    if income > 4500:
        return 0.050
    return 0.06


def calculate_income_approach_value(
    property_obj: Any,
    property_type: str,
    income: float,
    average_land_price: float,
    potential_floor_area: float,
    eval_area: float,
    tochi_area: float,
    scale_discount: float
) -> tuple[float, Any, Any]:
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


def calculate_appraisal_values(
    property_obj: Any,
    property_type: str,
    area: float,
    tatemono_area: float,
    tochi_area: float,
    chikunen: float,
    max_youseki: float,
    average_land_price: float,
    income: float,
    mkt_comparison_master: dict | None,
    address1: str,
    address2: str
) -> AppraisalValues:
    scale_discount = max(0.05, float((1000.0 / tochi_area) ** 0.35)) if tochi_area > 1000.0 else 1.0
    potential_floor_area = area if property_type == 'mansion' else tochi_area * (max_youseki / 100.0)

    # 原価法
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

    # 取引事例比較法
    eval_area = area if property_type == 'mansion' else tatemono_area
    eval_area = 50.0 if eval_area <= 0 else eval_area
    mkt_comparison_val = calculate_mkt_comparison_value(
        mkt_comparison_master, address1, address2, property_type, chikunen, eval_area, average_land_price
    )

    # 収益還元法
    income_approach_val, gross_yield, annual_rent = calculate_income_approach_value(
        property_obj, property_type, income, average_land_price, potential_floor_area,
        eval_area, tochi_area, scale_discount
    )

    return AppraisalValues(
        potential_floor_area=potential_floor_area,
        scale_discount=scale_discount,
        cost_approach_value=cost_approach_value,
        mkt_comparison_value=mkt_comparison_val,
        income_approach_value=income_approach_val,
        gross_yield=gross_yield,
        annual_rent=annual_rent,
    )


def _fallback_road_dimensions(raw_setsudou: str, road_width: Any, maguchi: Any) -> tuple[float, float]:
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


def _fallback_road_classification(raw_setsudou: str, direction_str: str, type_str: str) -> tuple[str, str]:
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


def _extract_road_specs(property_obj: Any) -> tuple[float, float, str, str, str, str]:
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


def _calculate_road_factors(
    tochi_area: float,
    maguchi_val: float,
    road_width_val: float,
    road_direction_str: str,
    road_structure_str: str,
    youto_chiiki: str,
    max_youseki: float
) -> tuple[float, float, float, float]:
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


def calculate_tochi_appraisal_factors(
    property_obj: Any,
    property_type: str,
    tochi_area: float,
    max_youseki: float,
    average_land_price: float,
    setback_ratio_temp: float
) -> TochiAppraisalFactors:
    if property_type not in ['tochi', 'kodate', 'apartment']:
        return TochiAppraisalFactors(
            maguchi_val=6.0,
            road_width_val=4.0,
            setback_ratio=0.0,
            actual_volume_limit=max_youseki,
            volume_digest_factor=1.0,
            road_condition_factor=1.0,
            frontage_penalty_factor=1.0,
            residual_land_value=0.0,
            road_direction_str="",
            road_type_str="",
            road_structure_str="",
            chimoku_str="",
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

    return TochiAppraisalFactors(
        maguchi_val=maguchi_val,
        road_width_val=road_width_val,
        setback_ratio=setback_ratio_temp,
        actual_volume_limit=actual_volume_limit,
        volume_digest_factor=volume_digest_factor,
        road_condition_factor=road_condition_factor,
        frontage_penalty_factor=frontage_penalty_factor,
        residual_land_value=residual_land_value,
        road_direction_str=road_direction_str,
        road_type_str=road_type_str,
        road_structure_str=road_structure_str,
        chimoku_str=chimoku_str,
    )


# Backward compatibility aliases
_calculate_appraisal_values = calculate_appraisal_values
_calculate_tochi_appraisal_factors = calculate_tochi_appraisal_factors
