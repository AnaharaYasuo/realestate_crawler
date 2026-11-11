"""
地域・物件状態に基づく期待表面/実質利回り算定 ＆ 周辺賃料ベース10年保有DCF理論価格算出モジュール (Issue #1349)

【制約・設計原則】
1. AI（LLM / Gemini API 等）完全不使用: 100%決定論的・高速なマスタ参照＆数理モデルのみで完結。
2. ターゲットリーク完全遮断: 売出価格 (`price`) および掲載表面利回り (`grossYield`) は一切参照しない。
3. 全物件種別対応: `mansion`, `kodate`, `apartment`, `tochi` および各種投資系サブタイプに対応。
"""

import datetime
import math
from dataclasses import dataclass
from typing import Any

from package.ml.features.appraisal import calculate_tochi_appraisal_factors
from package.ml.features.constants import LIFESPAN, REPLACEMENT_COSTS
from package.ml.features.legal_furuya import extract_combined_text_for_prop
from package.ml.features.parsers import (
    calculate_area_and_setback,
    calculate_chikunen_feature,
    calculate_shin_taishin,
    extract_clean_address,
    extract_traffic_and_walk_min,
    parse_floor_features,
    parse_kouzou,
    safe_float,
)
from package.ml.features.reference_data import (
    blend_land_prices,
    calculate_effective_walk_min,
    extract_macro_features,
    query_cap_rate_benchmark,
    query_future_population_features,
    query_hazard_features,
    query_municipal_potential,
    query_rent_market_potential,
    query_station_volume,
    resolve_zone_limits,
)
from package.utils import converter

PTYPE_MANSION = "mansion"
PTYPE_KODATE = "kodate"
PTYPE_APARTMENT = "apartment"
PTYPE_TOCHI = "tochi"
STRUCT_SRC = "SRC"
STRUCT_RC = "RC"
STRUCT_DEFAULT = "default"
TERM_UNBUILDABLE = "再建築不可"

_HOLDING_YEARS = 10
_DISCOUNT_ILLIQUIDITY_SPREAD_PCT = 0.40
_SELLING_COST_RATIO = 0.035
_RENTABLE_RATIO_DEV = 0.82

_STRUCT_RENT_FACTOR: dict[str, float] = {
    STRUCT_SRC: 1.07,
    STRUCT_RC: 1.05,
    "S": 1.01,
    "LS": 0.99,
    "W": 0.95,
    STRUCT_DEFAULT: 0.98,
}

_STRUCT_AGE_DECAY: dict[str, tuple[float, float]] = {
    STRUCT_SRC: (0.0070, 0.66),
    STRUCT_RC: (0.0075, 0.65),
    "S": (0.0090, 0.60),
    "LS": (0.0095, 0.58),
    "W": (0.0110, 0.54),
    STRUCT_DEFAULT: (0.0095, 0.58),
}

_STRUCT_CAP_SPREAD: dict[str, float] = {
    STRUCT_SRC: -0.10,
    STRUCT_RC: 0.00,
    "S": 0.30,
    "LS": 0.45,
    "W": 0.70,
    STRUCT_DEFAULT: 0.35,
}

_RENO_CAPEX_MAN: dict[str, float] = {
    "tier_none": 0.0,
    "tier_light": 80.0,
    "tier_medium": 220.0,
    "tier_heavy": 480.0,
    "tier_full": 850.0,
}


@dataclass(slots=True, frozen=True)
class DCFValuationResult:
    """AI不使用の期待利回り・想定賃料・10年DCF理論価格算出結果"""

    expected_gross_yield: float
    expected_net_yield: float
    estimated_annual_rent: int
    dcf_theoretical_price: int


@dataclass(slots=True, frozen=True)
class _PropertyContext:
    norm_type: str
    address1: str
    address2: str
    station1: str
    kouzou_cat: str
    chikunen: float
    effective_walk_min: float
    senyu_area: float
    tatemono_area: float
    tochi_area: float
    max_youseki: float
    actual_volume_limit: float
    scale_discount: float
    avg_land_price: float
    income: float
    passenger_volume: float
    pop_density: float
    future_pop_change: float
    flood_risk: int
    landslide_risk: int
    jgb_10y: float
    combined_text: str


def _get_val(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    val = getattr(obj, name, default)
    if hasattr(val, "_mock_name") or type(val).__name__ in ("MagicMock", "AsyncMock", "Mock"):
        return default
    return val


def _normalize_ptype(property_type: str, property_obj: Any) -> str:
    raw = (property_type or str(_get_val(property_obj, "propertyType", "")) or "").strip().lower()
    cleaned = raw.replace("_", "")
    if cleaned == PTYPE_TOCHI or "land" in cleaned:
        return PTYPE_TOCHI
    if "kodate" in cleaned:
        return PTYPE_KODATE
    if cleaned == PTYPE_MANSION:
        return PTYPE_MANSION
    if any(k in cleaned for k in (PTYPE_APARTMENT, "invest", "building")):
        return PTYPE_APARTMENT
    return PTYPE_MANSION


def _resolve_chikunen(property_obj: Any, norm_type: str, base_date: datetime.date) -> float:
    if norm_type == PTYPE_TOCHI:
        return 0.0
    explicit_age = _get_val(property_obj, "chikunen", None)
    if explicit_age is not None:
        parsed_age = safe_float(explicit_age, None)
        if parsed_age is not None and parsed_age >= 0.0:
            return float(parsed_age)
    age, _ = calculate_chikunen_feature(property_obj, norm_type, base_date)
    return max(0.0, float(age))


def _build_property_context(property_obj: Any, property_type: str) -> _PropertyContext:
    norm_type = _normalize_ptype(property_type, property_obj)
    base_date = datetime.date.today()
    address1, address2, station1, _ = extract_clean_address(property_obj)
    max_youseki, _, _, _, _ = resolve_zone_limits(property_obj)
    avg_land_price, _, _, _ = blend_land_prices(address1, address2, max_youseki)
    _, raw_inc, _, _, pop_density = query_municipal_potential(address1, address2)
    income = float(raw_inc) if raw_inc is not None else 3600.0
    st_vol = query_station_volume(station1)
    passenger_volume = float(st_vol) if st_vol is not None else 8000.0
    walk_min, bus_min, bus_walk, bus_use = extract_traffic_and_walk_min(property_obj)
    eff_walk = calculate_effective_walk_min(walk_min, bus_use, bus_min, bus_walk, pop_density)
    senyu_area, tatemono_area, tochi_area, setback_ratio = calculate_area_and_setback(property_obj, norm_type)

    if norm_type in (PTYPE_APARTMENT, PTYPE_KODATE) and tatemono_area <= 0.0:
        tatemono_area = float(safe_float(_get_val(property_obj, "buildingArea", 0.0), 0.0) or senyu_area)
    if norm_type != PTYPE_MANSION and tochi_area <= 0.0:
        tochi_area = float(safe_float(_get_val(property_obj, "landArea", 0.0), 0.0))

    base_scale = 300.0 if norm_type == PTYPE_APARTMENT else 150.0
    scale_discount = max(0.15, float((base_scale / tochi_area) ** 0.18)) if tochi_area > base_scale else 1.0
    tochi_factors = calculate_tochi_appraisal_factors(
        property_obj, norm_type, tochi_area, max_youseki, float(avg_land_price), setback_ratio, scale_discount
    )
    kouzou_raw = str(_get_val(property_obj, "kouzou", "") or _get_val(property_obj, "structure", "") or "")
    kouzou_cat = parse_kouzou(kouzou_raw)
    if kouzou_cat == STRUCT_DEFAULT:
        kouzou_cat = STRUCT_RC if norm_type in (PTYPE_MANSION, PTYPE_TOCHI) else "W"

    chikunen = _resolve_chikunen(property_obj, norm_type, base_date)
    future_pop_change, _, _, _ = query_future_population_features(address1, address2)
    flood_risk, landslide_risk = query_hazard_features(address1, address2)
    _, jgb_10y, _, _, _ = extract_macro_features(base_date, norm_type)
    combined_text = extract_combined_text_for_prop(property_obj)

    return _PropertyContext(
        norm_type=norm_type,
        address1=address1,
        address2=address2,
        station1=station1,
        kouzou_cat=kouzou_cat,
        chikunen=chikunen,
        effective_walk_min=eff_walk,
        senyu_area=senyu_area,
        tatemono_area=tatemono_area,
        tochi_area=tochi_area,
        max_youseki=max_youseki,
        actual_volume_limit=tochi_factors.actual_volume_limit,
        scale_discount=scale_discount,
        avg_land_price=float(avg_land_price),
        income=income,
        passenger_volume=passenger_volume,
        pop_density=pop_density,
        future_pop_change=future_pop_change,
        flood_risk=flood_risk,
        landslide_risk=landslide_risk,
        jgb_10y=jgb_10y,
        combined_text=combined_text,
    )


def _resolve_layout_bucket(property_obj: Any, unit_area: float) -> str:
    madori = str(_get_val(property_obj, "madori", "") or "").upper().strip()
    for token in ("1LDK", "2LDK", "3LDK", "1DK", "2DK", "3DK", "1R", "1K", "2K", "3K"):
        if token in madori:
            return token
    if "4" in madori or "5" in madori:
        return "4LDK+"
    if unit_area < 28.0:
        return "1K"
    if unit_area < 48.0:
        return "1LDK"
    if unit_area < 68.0:
        return "2LDK"
    return "3LDK"


def _resolve_rent_areas(property_obj: Any, ctx: _PropertyContext) -> tuple[float, float]:
    """(賃貸対象延床面積, 1戸あたり基準専有面積) を算出する"""
    if ctx.norm_type == PTYPE_MANSION:
        area = ctx.senyu_area if ctx.senyu_area > 0.0 else 55.0
        return area, area
    if ctx.norm_type == PTYPE_KODATE:
        area = ctx.tatemono_area if ctx.tatemono_area > 0.0 else 90.0
        return area, area
    if ctx.norm_type == PTYPE_TOCHI:
        land_m2 = ctx.tochi_area if ctx.tochi_area > 0.0 else 100.0
        eff_far = max(60.0, min(ctx.max_youseki, ctx.actual_volume_limit))
        rentable_m2 = land_m2 * (eff_far / 100.0) * _RENTABLE_RATIO_DEV
        return max(30.0, rentable_m2), 40.0

    total_m2 = ctx.tatemono_area if ctx.tatemono_area > 0.0 else 180.0
    soukosu = safe_float(_get_val(property_obj, "soukosu", None), 0.0) or 0.0
    unit_m2 = (total_m2 * 0.88 / soukosu) if soukosu >= 1.0 else min(45.0, max(22.0, total_m2 / 6.0))
    return total_m2 * 0.90, max(16.0, unit_m2)


def _fallback_regional_rent_per_sqm(ctx: _PropertyContext) -> float:
    land_man = max(2.0, ctx.avg_land_price / 10000.0)
    from_land = 850.0 + 235.0 * math.sqrt(land_man)
    inc_factor = min(1.30, max(0.80, (ctx.income / 3600.0) ** 0.35))
    st_factor = min(1.18, max(0.90, 0.86 + 0.04 * math.log10(max(500.0, ctx.passenger_volume))))
    return min(8500.0, max(950.0, from_land * inc_factor * st_factor))


def _resolve_base_rent_per_sqm(property_obj: Any, ctx: _PropertyContext, unit_area: float) -> float:
    b_type = PTYPE_APARTMENT if ctx.norm_type == PTYPE_TOCHI else ctx.norm_type
    l_type = _resolve_layout_bucket(property_obj, unit_area)
    hit = query_rent_market_potential(
        prefecture=ctx.address1,
        city=ctx.address2,
        station_name=ctx.station1,
        building_type=b_type,
        layout_type=l_type,
    )
    if hit is not None and hit[0] > 0:
        return float(hit[0])
    return _fallback_regional_rent_per_sqm(ctx)


def _calc_walk_rent_factor(effective_walk_min: float) -> float:
    if effective_walk_min <= 5.0:
        return 1.05 - 0.004 * effective_walk_min
    if effective_walk_min <= 15.0:
        return 1.03 - 0.010 * (effective_walk_min - 5.0)
    return max(0.74, 0.93 - 0.013 * (effective_walk_min - 15.0))


def _calc_floor_and_quality_rent_factor(
    property_obj: Any,
    ctx: _PropertyContext,
    interior_score: float,
    layout_score: float,
) -> float:
    factor = 1.0
    if ctx.norm_type == PTYPE_MANSION:
        fl_feats = parse_floor_features(
            _get_val(property_obj, "kaisu", None) or _get_val(property_obj, "shozaikai", None),
            _get_val(property_obj, "chijoKaisu", None) or _get_val(property_obj, "tatemonoKaisu", None),
            ctx.combined_text,
        )
        if fl_feats["is_first_floor"] >= 0.5:
            factor *= 0.96
        else:
            factor *= min(1.08, 1.0 + max(0.0, fl_feats["floor_number"] - 2.0) * 0.006)

    saikou_text = f"{_get_val(property_obj, 'saikou', '') or ''} {_get_val(property_obj, 'kadobeya', '') or ''} {ctx.combined_text}"
    if "南" in saikou_text:
        factor *= 1.02
    if "角部屋" in saikou_text or "角住戸" in saikou_text:
        factor *= 1.02

    clamped_int = min(5.0, max(1.0, float(interior_score)))
    clamped_lay = min(5.0, max(1.0, float(layout_score)))
    quality_delta = ((clamped_int - 3.0) * 0.035) + ((clamped_lay - 3.0) * 0.015)
    return factor * (1.0 + quality_delta)


def estimate_market_rent(
    property_obj: Any,
    property_type: str,
    interior_score: float = 3.0,
    layout_score: float = 3.0,
    _ctx: _PropertyContext | None = None,
) -> int:
    """周辺家賃相場マスタ＋物件スペック味付けから適正年間満室想定賃料（円/年）を決定論的に推計する。"""
    ctx = _ctx or _build_property_context(property_obj, property_type)
    rentable_area, unit_area = _resolve_rent_areas(property_obj, ctx)
    base_sqm_rent = _resolve_base_rent_per_sqm(property_obj, ctx, unit_area)

    area_factor = min(1.24, max(0.78, (50.0 / max(15.0, unit_area)) ** 0.12))
    decay_rate, floor_ratio = _STRUCT_AGE_DECAY.get(ctx.kouzou_cat, _STRUCT_AGE_DECAY[STRUCT_DEFAULT])
    age_factor = 1.0 if ctx.norm_type == PTYPE_TOCHI else max(floor_ratio, 1.0 - decay_rate * ctx.chikunen)
    walk_factor = _calc_walk_rent_factor(ctx.effective_walk_min)
    struct_factor = _STRUCT_RENT_FACTOR.get(ctx.kouzou_cat, _STRUCT_RENT_FACTOR[STRUCT_DEFAULT])
    qual_factor = _calc_floor_and_quality_rent_factor(property_obj, ctx, interior_score, layout_score)

    monthly_rent = rentable_area * base_sqm_rent * area_factor * age_factor * walk_factor * struct_factor * qual_factor
    annual_rent = int(round(max(120_000.0, monthly_rent * 12.0), -3))
    return max(120_000, annual_rent)


def _resolve_benchmark_asset_type(ctx: _PropertyContext) -> str:
    if ctx.norm_type == PTYPE_MANSION:
        return PTYPE_MANSION
    if ctx.norm_type == PTYPE_KODATE:
        return PTYPE_KODATE
    return "apartment_rc" if ctx.kouzou_cat in (STRUCT_RC, STRUCT_SRC) else "apartment_wood"


def _resolve_anchor_net_cap_and_vacancy(ctx: _PropertyContext) -> tuple[float, float, float]:
    """(基準NCFキャップレート%, 標準OPEX比率0-1, 基準空室率0-1) を返す"""
    asset_key = _resolve_benchmark_asset_type(ctx)
    bench = query_cap_rate_benchmark(ctx.address1, ctx.address2, ctx.station1, asset_key)
    std_opex = (float(bench.standard_opex_ratio) / 100.0) if bench and bench.standard_opex_ratio else 0.18
    vac_base = (float(bench.rental_vacancy_rate) / 100.0) if bench and bench.rental_vacancy_rate is not None else 0.065

    if bench and bench.expected_net_cap_rate is not None:
        return float(bench.expected_net_cap_rate), std_opex, vac_base
    if bench and bench.expected_gross_yield is not None:
        implied_net = float(bench.expected_gross_yield) * max(0.55, 1.0 - std_opex - vac_base)
        return max(3.0, implied_net), std_opex, vac_base

    rf = max(0.3, min(2.5, ctx.jgb_10y))
    if ctx.avg_land_price >= 800_000:
        fallback_net = 3.1 + rf * 0.35
    elif ctx.avg_land_price >= 300_000:
        fallback_net = 3.9 + rf * 0.40
    elif ctx.avg_land_price >= 120_000:
        fallback_net = 4.7 + rf * 0.45
    else:
        fallback_net = 5.6 + rf * 0.50
    return fallback_net, std_opex, vac_base


def _calc_regional_and_condition_spread(
    property_obj: Any,
    ctx: _PropertyContext,
    interior_score: float,
) -> float:
    spread = _STRUCT_CAP_SPREAD.get(ctx.kouzou_cat, 0.35)
    lifespan = float(LIFESPAN.get(ctx.kouzou_cat, 30))
    age_ratio = min(1.8, ctx.chikunen / max(1.0, lifespan)) if ctx.norm_type != PTYPE_TOCHI else 0.15
    spread += age_ratio * 0.85

    if ctx.norm_type != PTYPE_TOCHI and calculate_shin_taishin(property_obj, ctx.chikunen) == 0:
        spread += 0.55
    if ctx.effective_walk_min > 10.0:
        spread += min(1.10, (ctx.effective_walk_min - 10.0) * 0.065)
    if ctx.future_pop_change < -5.0:
        spread += min(0.80, abs(ctx.future_pop_change + 5.0) * 0.04)
    elif ctx.future_pop_change > 2.0:
        spread -= min(0.25, (ctx.future_pop_change - 2.0) * 0.03)

    spread += (ctx.flood_risk * 0.08) + (ctx.landslide_risk * 0.10)
    spread -= (min(5.0, max(1.0, float(interior_score))) - 3.0) * 0.12
    return spread


def _calc_legal_and_defect_spread(property_obj: Any, combined_text: str) -> float:
    spread = 0.0
    tochikenri = str(_get_val(property_obj, "tochikenri", "") or "")
    rights_text = f"{tochikenri} {combined_text}"
    if any(k in rights_text for k in ("借地", "地上権", "賃借", "定借")):
        spread += 1.15
    if TERM_UNBUILDABLE in rights_text:
        spread += 2.40
    if "市街化調整" in rights_text or "調整区域" in rights_text:
        spread += 1.20
    if "告知事項" in rights_text or "心理的瑕疵" in rights_text:
        spread += 1.00
    if "私道負担有" in rights_text or "私道負担あり" in rights_text:
        spread += 0.25
    return spread


def _extract_annual_land_rent_yen(property_obj: Any) -> int:
    raw_chidai = _get_val(property_obj, "chidai", None)
    if raw_chidai is None:
        chidai_str = str(_get_val(property_obj, "chidaiStr", "") or "")
        if chidai_str:
            raw_chidai = converter.parse_chidai(chidai_str)
    val = safe_float(raw_chidai, 0.0) or 0.0
    return int(val * 12.0) if val > 0.0 else 0


def _resolve_opex_and_vacancy(
    property_obj: Any,
    ctx: _PropertyContext,
    estimated_annual_rent: int,
    std_opex: float,
    vac_base: float,
) -> tuple[float, float]:
    age_vac_add = 0.0 if ctx.norm_type == PTYPE_TOCHI else min(0.08, ctx.chikunen * 0.0016)
    walk_vac_add = max(0.0, min(0.05, (ctx.effective_walk_min - 10.0) * 0.003))
    vacancy_rate = min(0.24, max(0.03, vac_base + age_vac_add + walk_vac_add))

    if ctx.norm_type == PTYPE_MANSION and estimated_annual_rent > 0:
        kanri = safe_float(_get_val(property_obj, "kanrihi", 0), 0.0) or 0.0
        syuzen = safe_float(_get_val(property_obj, "syuzenTsumitate", 0), 0.0) or 0.0
        if kanri > 200_000.0:
            kanri /= 10000.0
        if syuzen > 200_000.0:
            syuzen /= 10000.0
        hoa_annual = (kanri + syuzen) * 12.0
        if hoa_annual > 0.0:
            hoa_ratio = hoa_annual / float(estimated_annual_rent)
            opex_ratio = min(0.55, max(0.12, hoa_ratio + 0.07))
            return vacancy_rate, opex_ratio

    age_opex_add = 0.0 if ctx.norm_type == PTYPE_TOCHI else min(0.07, ctx.chikunen * 0.0015)
    opex_ratio = min(0.45, max(0.12, std_opex + age_opex_add))
    return vacancy_rate, opex_ratio


def calculate_expected_yields(
    property_obj: Any,
    property_type: str,
    estimated_annual_rent: int,
    interior_score: float = 3.0,
    _ctx: _PropertyContext | None = None,
) -> tuple[float, float, float, float]:
    """
    地域・物件状態に基づき (expected_gross_yield%, expected_net_yield%, vacancy_rate, opex_ratio) を算出する。
    """
    ctx = _ctx or _build_property_context(property_obj, property_type)
    anchor_net, std_opex, vac_base = _resolve_anchor_net_cap_and_vacancy(ctx)
    cond_spread = _calc_regional_and_condition_spread(property_obj, ctx, interior_score)
    legal_spread = _calc_legal_and_defect_spread(property_obj, ctx.combined_text)

    net_yield = min(15.0, max(2.8, anchor_net + cond_spread + legal_spread))
    vacancy_rate, opex_ratio = _resolve_opex_and_vacancy(
        property_obj, ctx, estimated_annual_rent, std_opex, vac_base
    )
    land_rent_yen = _extract_annual_land_rent_yen(property_obj)
    land_rent_ratio = (land_rent_yen / float(estimated_annual_rent)) if estimated_annual_rent > 0 else 0.0

    ncf_margin = max(0.32, (1.0 - vacancy_rate) - opex_ratio - min(0.25, land_rent_ratio))
    gross_yield = min(28.0, max(net_yield + 0.5, net_yield / ncf_margin))
    return round(gross_yield, 2), round(net_yield, 2), vacancy_rate, opex_ratio


def _resolve_rights_ratio(combined_text: str, chikunen: float) -> float:
    if "底地" in combined_text or "貸地" in combined_text:
        return 0.20
    if "定期" in combined_text or "定借" in combined_text:
        rem = max(0.20, (50.0 - chikunen) / 50.0) if chikunen > 0 else 0.50
        return 0.70 * rem
    if any(k in combined_text for k in ("借地", "地上権", "賃借")):
        return 0.65
    return 1.0


def _calc_land_residual_man(ctx: _PropertyContext) -> float:
    rights_ratio = _resolve_rights_ratio(ctx.combined_text, ctx.chikunen)
    unbuildable_discount = 0.55 if TERM_UNBUILDABLE in ctx.combined_text else 1.0
    if ctx.norm_type == PTYPE_MANSION:
        eff_area = ctx.senyu_area if ctx.senyu_area > 0.0 else 55.0
        return (eff_area * 0.20) * (ctx.avg_land_price / 10000.0) * rights_ratio * unbuildable_discount
    eff_land = ctx.tochi_area if ctx.tochi_area > 0.0 else 100.0
    return eff_land * (ctx.avg_land_price / 10000.0) * ctx.scale_discount * rights_ratio * unbuildable_discount


def _estimate_tochi_dev_residual_and_capex(
    property_obj: Any,
    ctx: _PropertyContext,
    lifespan: float,
    unit_cost: float,
) -> tuple[float, float]:
    rentable_area, _ = _resolve_rent_areas(property_obj, ctx)
    gross_build_area = rentable_area / _RENTABLE_RATIO_DEV
    dev_cost_man = gross_build_area * max(22.0, unit_cost * 1.08)
    if "古家" in ctx.combined_text and "更地渡" not in ctx.combined_text:
        dev_cost_man += 180.0
    rem_y10 = max(0.15, (lifespan - 10.0) / max(1.0, lifespan))
    bldg_y10 = gross_build_area * unit_cost * rem_y10
    return bldg_y10, dev_cost_man


def _estimate_y10_residuals_and_initial_capex(
    property_obj: Any,
    ctx: _PropertyContext,
) -> tuple[float, float, float]:
    """(10年後土地残存価値[万], 10年後建物残存価値[万], 初期CapEx・開発建築費[万])"""
    land_man = _calc_land_residual_man(ctx)
    lifespan = float(LIFESPAN.get(ctx.kouzou_cat, 30))
    unit_cost = float(REPLACEMENT_COSTS.get(ctx.kouzou_cat, 20.0))

    if ctx.norm_type == PTYPE_TOCHI:
        bldg_y10, dev_cost_man = _estimate_tochi_dev_residual_and_capex(property_obj, ctx, lifespan, unit_cost)
        return land_man, bldg_y10, dev_cost_man

    raw_bldg = ctx.senyu_area if ctx.norm_type == PTYPE_MANSION else ctx.tatemono_area
    bldg_area = raw_bldg if raw_bldg > 0.0 else 60.0
    age_y10 = ctx.chikunen + float(_HOLDING_YEARS)
    if age_y10 >= lifespan:
        bldg_y10 = 0.0 if ctx.norm_type == PTYPE_MANSION else -max(80.0, bldg_area * 0.04)
    else:
        bldg_y10 = bldg_area * unit_cost * ((lifespan - age_y10) / lifespan)

    reno_tier = str(_get_val(property_obj, "renovation_budget_tier", "") or "")
    init_capex = _RENO_CAPEX_MAN.get(reno_tier, 0.0)
    if init_capex <= 0.0 and ctx.chikunen >= 32.0:
        init_capex = min(350.0, bldg_area * 1.8)
    return land_man, bldg_y10, init_capex


def calculate_dcf_theoretical_price(
    estimated_annual_rent: int,
    expected_net_yield: float,
    vacancy_rate: float,
    opex_ratio: float,
    annual_land_rent_yen: int,
    land_residual_man: float,
    bldg_residual_y10_man: float,
    initial_capex_man: float = 0.0,
    rent_decay_rate: float = 0.007,
    capex_ratio: float = 0.04,
    exit_spread_pct: float = 0.65,
) -> int:
    """10年保有DCF法により割引現在価値＋10年後復帰価値からDCF理論価格（万円）を逆算する。"""
    if estimated_annual_rent <= 0 or expected_net_yield <= 0.0:
        return 0

    g0_man = float(estimated_annual_rent) / 10000.0
    land_rent_man = float(annual_land_rent_yen) / 10000.0
    discount_rate = (expected_net_yield + _DISCOUNT_ILLIQUIDITY_SPREAD_PCT) / 100.0
    exit_cap_rate = (expected_net_yield + exit_spread_pct) / 100.0

    pv_ncf_sum = 0.0
    for t in range(1, _HOLDING_YEARS + 1):
        gt = g0_man * ((1.0 - rent_decay_rate) ** (t - 1))
        vt = min(0.28, vacancy_rate + 0.0025 * (t - 1))
        ncf_t = gt * (1.0 - vt - opex_ratio - capex_ratio) - land_rent_man
        pv_ncf_sum += ncf_t / ((1.0 + discount_rate) ** t)

    g11 = g0_man * ((1.0 - rent_decay_rate) ** _HOLDING_YEARS)
    v11 = min(0.30, vacancy_rate + 0.0025 * _HOLDING_YEARS)
    ncf_11 = max(0.0, g11 * (1.0 - v11 - opex_ratio - capex_ratio) - land_rent_man)
    income_tv = (ncf_11 / exit_cap_rate) * (1.0 - _SELLING_COST_RATIO)
    physical_floor_tv = max(0.0, land_residual_man + bldg_residual_y10_man) * (1.0 - _SELLING_COST_RATIO)
    terminal_value = max(income_tv, physical_floor_tv * 0.85)
    pv_tv = terminal_value / ((1.0 + discount_rate) ** _HOLDING_YEARS)

    total_dcf_man = pv_ncf_sum + pv_tv - initial_capex_man
    if total_dcf_man <= 0.0 and land_residual_man > 0.0:
        total_dcf_man = land_residual_man * 0.65
    return max(0, round(total_dcf_man))


def _resolve_rent_decay_and_capex_ratio(ctx: _PropertyContext) -> tuple[float, float]:
    if ctx.future_pop_change < -5.0:
        pop_adj = 0.0015
    elif ctx.future_pop_change > 2.0:
        pop_adj = -0.0015
    else:
        pop_adj = 0.0
    rent_decay = min(0.014, max(0.004, 0.007 + pop_adj))

    if ctx.chikunen < 10.0:
        capex_ratio = 0.030
    elif ctx.chikunen < 25.0:
        capex_ratio = 0.045
    else:
        capex_ratio = 0.060
    return rent_decay, capex_ratio


def evaluate_dcf_and_yields(
    property_obj: Any,
    property_type: str,
    interior_score: float = 3.0,
    layout_score: float = 3.0,
) -> DCFValuationResult:
    """
    単一物件オブジェクトまたは辞書に対して、AI不使用で期待表面利回り・期待実質利回り・想定年間賃料・10年DCF理論価格を算出する。
    """
    ctx = _build_property_context(property_obj, property_type)
    annual_rent = estimate_market_rent(
        property_obj, property_type, interior_score=interior_score, layout_score=layout_score, _ctx=ctx
    )
    gross_yield, net_yield, vac_rate, opex_ratio = calculate_expected_yields(
        property_obj, property_type, estimated_annual_rent=annual_rent, interior_score=interior_score, _ctx=ctx
    )
    land_rent_yen = _extract_annual_land_rent_yen(property_obj)
    land_res_man, bldg_y10_man, init_capex_man = _estimate_y10_residuals_and_initial_capex(property_obj, ctx)
    rent_decay, capex_ratio = _resolve_rent_decay_and_capex_ratio(ctx)
    exit_spread = 0.50 if ctx.kouzou_cat in (STRUCT_RC, STRUCT_SRC) else 0.75

    dcf_price = calculate_dcf_theoretical_price(
        estimated_annual_rent=annual_rent,
        expected_net_yield=net_yield,
        vacancy_rate=vac_rate,
        opex_ratio=opex_ratio,
        annual_land_rent_yen=land_rent_yen,
        land_residual_man=land_res_man,
        bldg_residual_y10_man=bldg_y10_man,
        initial_capex_man=init_capex_man,
        rent_decay_rate=rent_decay,
        capex_ratio=capex_ratio,
        exit_spread_pct=exit_spread,
    )
    if ctx.norm_type == PTYPE_TOCHI and TERM_UNBUILDABLE in ctx.combined_text:
        dcf_price = min(dcf_price, max(1, round(land_res_man * 0.75)))

    return DCFValuationResult(
        expected_gross_yield=gross_yield,
        expected_net_yield=net_yield,
        estimated_annual_rent=annual_rent,
        dcf_theoretical_price=dcf_price,
    )
