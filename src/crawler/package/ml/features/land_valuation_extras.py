"""
AI課金ゼロの決定論的土地・全種別評価特徴量モジュール (Issue #1360)

- 国土地理院 5m/10m 標高DEM微地形（標高・傾斜角・南ひな段方位・窪地深さ）連携
- 国交省実成約（XIT001 / 公式CSV）・掲載終了成約スプレッド連携
- インフラ引込・高低差擁壁・解体費の非比例固定費控除 (`estimated_fixed_cost_man`, `fixed_cost_per_sqm`)
- 戸建て・一棟アパート・区分マンション敷地権を含む土地構成要素分解 (`net_land_component_man`, `net_land_per_sqm`, `land_value_share`)
- 敷地レバレッジ・物理減価を保存する全4種別対応アンカー対数単価 (`anchor_log_unit_price`)
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any
import unicodedata

import numpy as np
import pandas as pd

from package.ml.features.parsers import _get_attr, safe_float
from package.utils.gsi_dem_terrain import lookup_cached_dem_features
from package.utils.mlit_transaction_data import lookup_transaction_benchmark

_ELEVATION_PREFIX_RE = re.compile(
    r"(?:道路面?より|隣地より|高低差|段差)[\s:：最大約概ね]{0,8}(\d{1,2}(?:\.\d{1,2})?)\s{0,5}[mｍ]"
)
_ELEVATION_SUFFIX_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})?)\s{0,5}[mｍ]\s{0,5}(?:高い|低い|の高低差|の段差)"
)
_ROAD_SHARE_STRIP_RE = re.compile(
    r"(?:私道|道路|通路|ゴミ置場|ごみ置場|集会所|提供公園|協定)[^\s、。]{0,8}持分\s{0,5}\d{1,4}\s{0,5}/\s{0,5}\d{1,4}"
)
_SUBJECT_SHARE_RE = re.compile(r"持分\s{0,5}\d{1,4}\s{0,5}/\s{0,5}\d{1,4}")

_WATER_UNCONNECTED_KW = ("上水道引込無", "水道引込無", "上水道なし", "水道なし", "井戸水", "前面道路本管無")
_SEWER_UNCONNECTED_KW = ("浄化槽", "汲取", "汲み取り", "下水引込無", "公共下水未整備")
_SEWER_CONNECTED_KW = ("公共下水", "本下水", "下水引込済")
_GAS_PROPANE_KW = ("プロパン", "LPガス", "ＬＰガス", "個別プロパン", "都市ガス引込無")
_UNSAFE_WALL_KW = ("間知石", "玉石", "大谷石", "空積み", "増積み", "がけ条例", "崖条例", "擁壁要", "擁壁やり替え")
_GENERAL_WALL_KW = ("擁壁", "法面", "のり面", "急傾斜")
_SAFE_WALL_KW = ("検査済証有", "新設擁壁", "RC擁壁築造済")
_MEASURED_BOUNDARY_KW = ("確定測量済", "確定測量渡", "確定測量後", "境界明示", "実測売買", "実測取引")
_CUL_DE_SAC_KW = ("行き止まり", "行止り", "行止まり", "袋小路", "ドン突き")
_SPECIAL_SHARE_KW = ("共有持分", "持分売買", "持分のみ", "底地のみ")


@dataclass(frozen=True)
class AnchorPricingInput:
    """理論アンカー対数㎡単価の算出パラメータ構造体"""

    property_type: str
    gross_area: float
    effective_tochi_area: float
    micro_land_price: float
    scale_discount: float
    frontage_penalty_factor: float
    road_condition_factor: float
    plot_shape_penalty: float
    rights_ratio: float
    is_saikenchiku_fuka: float
    is_shigaika_chousei: float
    fixed_cost_per_sqm: float
    cost_approach_value: float
    income_approach_value: float
    dcf_theoretical_value: float
    mkt_comparison_value: float = 0.0
    bldg_component_man: float = 0.0
    building_depreciation_ratio: float = 0.5
    mlit_tx_unit_price_man: float = 0.0
    dem_south_aspect_score: float = 0.0
    dem_depression_depth_m: float = 0.0


@dataclass(frozen=True)
class LandValuationContext:
    """決定論的土地・全種別評価特徴量の抽出コンテキスト"""

    property_obj: Any
    property_type: str
    combined_text: str
    gross_area: float
    effective_tochi_area: float
    tatemono_area: float
    chikunen: float
    micro_land_price: int
    average_land_price: int
    chome_infra_score: float
    maguchi_val: float
    road_width_val: float
    scale_discount: float
    road_condition_factor: float
    frontage_penalty_factor: float
    plot_shape_penalty: float
    rights_ratio: float
    is_saikenchiku_fuka: float
    is_shigaika_chousei: float
    furuya_demolition_cost: float
    cost_approach_value: float
    income_approach_value: float
    mkt_comparison_master: dict | None
    address1: str
    address2: str
    chome_group: str = ""
    latitude: float | None = None
    longitude: float | None = None
    mkt_comparison_value: float = 0.0
    building_depreciation_ratio: float = 0.5
    demolition_cost_discount: float = 0.0


def _evaluate_infra_connection(norm_text: str, chome_infra_score: float) -> tuple[float, float]:
    w_score, w_cost = (0.0, 95.0) if any(k in norm_text for k in _WATER_UNCONNECTED_KW) else (1.0, 0.0)

    if any(k in norm_text for k in _SEWER_UNCONNECTED_KW):
        s_score, s_cost = 0.35, 85.0
    elif any(k in norm_text for k in _SEWER_CONNECTED_KW) or chome_infra_score >= 0.90:
        s_score, s_cost = 1.0, 0.0
    else:
        s_score, s_cost = 0.75, 30.0

    if any(k in norm_text for k in _GAS_PROPANE_KW):
        g_score, g_cost = 0.55, 25.0
    elif "都市ガス" in norm_text or chome_infra_score >= 0.90:
        g_score, g_cost = 1.0, 0.0
    else:
        g_score, g_cost = 0.80, 0.0

    score = round(0.40 * w_score + 0.35 * s_score + 0.25 * g_score, 4)
    return score, round(w_cost + s_cost + g_cost, 2)


def _extract_elevation_diff_m(property_obj: Any, norm_text: str, dem_slope_deg: float = 0.0) -> float:
    attr_val = safe_float(_get_attr(property_obj, "ground_elevation_diff_m", None), None)
    if attr_val is not None and attr_val > 0:
        return round(float(attr_val), 2)
    for pattern in (_ELEVATION_PREFIX_RE, _ELEVATION_SUFFIX_RE):
        m = pattern.search(norm_text)
        if m:
            return round(safe_float(m.group(1), 0.0), 2)
    if any(k in norm_text for k in ("急傾斜", "がけ条例", "崖条例")):
        return 2.5
    if any(k in norm_text for k in ("ひな段", "雛段", "高台", "傾斜地", "法面")):
        return 1.5
    if dem_slope_deg >= 10.0:
        return round(math.tan(math.radians(min(35.0, dem_slope_deg))) * 3.5, 2)
    return 0.0


def _estimate_retaining_wall_cost(norm_text: str, elevation_diff_m: float, gross_area: float) -> float:
    if any(k in norm_text for k in _SAFE_WALL_KW):
        return 0.0
    wall_len = max(8.0, min(35.0, math.sqrt(max(40.0, gross_area))))
    has_unsafe = any(k in norm_text for k in _UNSAFE_WALL_KW)
    if elevation_diff_m >= 2.0 or has_unsafe:
        eff_h = max(1.8, elevation_diff_m)
        mult = 1.15 if has_unsafe else 1.0
        return round(min(2500.0, (6.5 + 8.5 * eff_h) * wall_len * mult), 2)
    if elevation_diff_m >= 0.8 or any(k in norm_text for k in _GENERAL_WALL_KW):
        return round(min(1500.0, max(80.0, max(1.0, elevation_diff_m) * 6.0 * wall_len)), 2)
    return 0.0


def _detect_special_sale_share(norm_text: str) -> float:
    if any(k in norm_text for k in _SPECIAL_SHARE_KW):
        return 1.0
    stripped = _ROAD_SHARE_STRIP_RE.sub("", norm_text)
    return 1.0 if _SUBJECT_SHARE_RE.search(stripped) else 0.0


def _calculate_subdivision_potential(
    effective_tochi_area: float,
    maguchi_val: float,
    road_width_val: float,
    is_saikenchiku_fuka: float,
    is_shigaika_chousei: float,
) -> float:
    if is_saikenchiku_fuka >= 0.5 or is_shigaika_chousei >= 0.5:
        return 0.0
    if effective_tochi_area < 140.0 or maguchi_val < 8.5 or road_width_val < 4.0:
        return 0.0
    possible_lots = min(4.0, math.floor(min(effective_tochi_area / 85.0, maguchi_val / 4.5)))
    if possible_lots < 2.0:
        return 0.0
    wide_road_bonus = 0.10 if road_width_val >= 5.0 else 0.0
    return round(min(1.0, (possible_lots - 1.0) * 0.45 + wide_road_bonus), 4)


def _compute_dcf_safe(property_obj: Any, property_type: str) -> float:
    try:
        from package.ml.dcf_valuation import evaluate_dcf_and_yields

        res = evaluate_dcf_and_yields(property_obj, property_type)
        return float(max(0, res.dcf_theoretical_price))
    except Exception:
        return 0.0


def _compute_kodate_residual_land_value(
    mkt_comparison_master: dict | None,
    address1: str,
    address2: str,
    effective_tochi_area: float,
    micro_land_price: float,
    scale_discount: float,
    road_condition_factor: float,
    frontage_penalty_factor: float,
    estimated_fixed_cost_man: float,
) -> float:
    if effective_tochi_area <= 0.0:
        return 0.0
    unit_man = micro_land_price / 10000.0
    if mkt_comparison_master:
        kodate_old = mkt_comparison_master.get((address1, address2, "kodate", 3))
        if kodate_old is not None and kodate_old > 0:
            unit_man = 0.65 * unit_man + 0.35 * max(0.5, float(kodate_old) * 0.72)
    gross_land = (
        effective_tochi_area
        * unit_man
        * scale_discount
        * road_condition_factor
        * frontage_penalty_factor
    )
    return round(max(0.0, gross_land - estimated_fixed_cost_man), 2)


def _resolve_legal_land_multipliers(
    property_type: str, is_saikenchiku_fuka: float, is_shigaika_chousei: float
) -> tuple[float, float]:
    """土地更地（建築不可＝0.25）と既存建物付き（既得権居住・賃貸可＝0.48）の法的減価率を区別する。"""
    saiken_pen = 0.25 if property_type == "tochi" else 0.48
    shigaika_pen = 0.35 if property_type == "tochi" else 0.50
    saiken_m = saiken_pen if is_saikenchiku_fuka >= 0.5 else 1.0
    shigaika_m = shigaika_pen if is_shigaika_chousei >= 0.5 else 1.0
    return saiken_m, shigaika_m


def _dem_terrain_multiplier(south_aspect: float, depression_m: float) -> float:
    adj = 1.0 + 0.035 * float(south_aspect) - 0.025 * max(0.0, float(depression_m) - 0.8)
    return min(1.05, max(0.88, adj))


def _compute_net_land_from_input(inp: AnchorPricingInput) -> float:
    denom = max(1.0, float(inp.gross_area))
    micro_man = max(0.05, float(inp.micro_land_price) / 10000.0)
    saiken_m, shigaika_m = _resolve_legal_land_multipliers(
        inp.property_type, inp.is_saikenchiku_fuka, inp.is_shigaika_chousei
    )
    dem_m = _dem_terrain_multiplier(inp.dem_south_aspect_score, inp.dem_depression_depth_m)
    if inp.property_type == "mansion":
        return max(0.0, (denom * 0.20) * micro_man * float(inp.rights_ratio) * shigaika_m)
    eff_land = max(0.0, float(inp.effective_tochi_area))
    gross_land = (
        eff_land
        * micro_man
        * float(inp.scale_discount)
        * float(inp.frontage_penalty_factor)
        * float(inp.road_condition_factor)
        * float(inp.plot_shape_penalty)
        * float(inp.rights_ratio)
        * saiken_m
        * shigaika_m
        * dem_m
    )
    fixed_man = float(inp.fixed_cost_per_sqm) * denom
    return max(0.0, gross_land - fixed_man)


def _compute_kodate_anchor_unit(inp: AnchorPricingInput, net_land_man: float, denom: float) -> float:
    phys_total = net_land_man + max(0.0, float(inp.bldg_component_man))
    has_severe_defect = inp.is_saikenchiku_fuka >= 0.5 or inp.is_shigaika_chousei >= 0.5
    if not has_severe_defect:
        ref_val = (
            float(inp.mlit_tx_unit_price_man) * denom
            if inp.mlit_tx_unit_price_man > 0
            else float(inp.mkt_comparison_value)
        )
        if ref_val > 0:
            phys_total = 0.80 * phys_total + 0.20 * ref_val
    return max(0.05, phys_total / denom)


def _compute_apartment_anchor_unit(inp: AnchorPricingInput, net_land_man: float, denom: float) -> float:
    phys_total = net_land_man + max(0.0, float(inp.bldg_component_man))
    saiken_m, shigaika_m = _resolve_legal_land_multipliers(
        inp.property_type, inp.is_saikenchiku_fuka, inp.is_shigaika_chousei
    )
    inc_candidates = [v for v in (inp.dcf_theoretical_value, inp.income_approach_value) if v and v > 0]
    inc_total = (sum(inc_candidates) / len(inc_candidates)) if inc_candidates else phys_total
    if saiken_m * shigaika_m < 0.95:
        inc_total *= saiken_m * shigaika_m
    dep = min(1.0, max(0.0, float(inp.building_depreciation_ratio)))
    w_phys = min(0.80, max(0.35, 0.35 + 0.45 * (1.0 - dep)))
    blended = max(w_phys * phys_total + (1.0 - w_phys) * inc_total, net_land_man * 0.92)
    return max(0.05, blended / denom)


def compute_anchor_log_unit_price(inp: AnchorPricingInput) -> float:
    """全物件種別（土地・戸建て・一棟アパート・マンション）の物理＋収益＋成約統合対数㎡単価 `log1p(万円/㎡)`。"""
    denom = max(1.0, float(inp.gross_area))
    net_land_man = _compute_net_land_from_input(inp)

    if inp.property_type == "tochi":
        net_unit = max(0.02, net_land_man / denom)
        has_defect = inp.is_saikenchiku_fuka >= 0.5 or inp.is_shigaika_chousei >= 0.5 or inp.rights_ratio < 0.9
        if inp.mlit_tx_unit_price_man > 0 and not has_defect:
            tx_adj = float(inp.mlit_tx_unit_price_man) * float(inp.plot_shape_penalty) * float(inp.road_condition_factor)
            net_unit = max(0.02, 0.80 * net_unit + 0.20 * tx_adj - float(inp.fixed_cost_per_sqm) * 0.2)
        return round(float(math.log1p(net_unit)), 6)

    if inp.property_type == "kodate":
        return round(float(math.log1p(_compute_kodate_anchor_unit(inp, net_land_man, denom))), 6)

    if inp.property_type == "apartment":
        return round(float(math.log1p(_compute_apartment_anchor_unit(inp, net_land_man, denom))), 6)

    candidates = [
        v
        for v in (inp.cost_approach_value, inp.mkt_comparison_value, inp.dcf_theoretical_value)
        if v and v > 0
    ]
    base_unit = (sum(candidates) / len(candidates) / denom) if candidates else max(0.05, net_land_man / denom)
    if inp.mlit_tx_unit_price_man > 0:
        base_unit = 0.75 * base_unit + 0.25 * float(inp.mlit_tx_unit_price_man)
    return round(float(math.log1p(max(0.05, base_unit))), 6)


def _col_series(df: pd.DataFrame, col: str, default: float | pd.Series) -> pd.Series:
    if col not in df.columns:
        if isinstance(default, pd.Series):
            return default.astype(float)
        return pd.Series(np.full(len(df), float(default), dtype=float), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(default).astype(float)


def _col_flag_multiplier(df: pd.DataFrame, col: str, penalty: float) -> np.ndarray:
    if col not in df.columns:
        return np.ones(len(df), dtype=float)
    vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    return np.where(vals >= 0.5, penalty, 1.0)


def _vectorized_net_land_man(df: pd.DataFrame, property_type: str, denom: pd.Series) -> tuple[pd.Series, np.ndarray]:
    micro_man = (_col_series(df, "micro_land_price", 80000.0) / 10000.0).clip(lower=0.05)
    eff_area = _col_series(df, "effective_tochi_menseki", denom if property_type == "tochi" else 0.0).clip(lower=0.0)
    scale_d = _col_series(df, "scale_discount", 1.0)
    front_f = _col_series(df, "frontage_penalty_factor", 1.0)
    road_f = _col_series(df, "road_condition_factor", 1.0)
    shape_f = _col_series(df, "plot_shape_penalty", 1.0)
    rights_f = _col_series(df, "rights_ratio", 1.0)
    fixed_sqm = _col_series(df, "fixed_cost_per_sqm", 0.0)
    saiken = _col_flag_multiplier(df, "is_saikenchiku_fuka", 0.25 if property_type == "tochi" else 0.48)
    shigaika = _col_flag_multiplier(df, "is_shigaika_chousei", 0.35 if property_type == "tochi" else 0.50)

    qual_mult = (scale_d * front_f * road_f * shape_f * rights_f).to_numpy(dtype=float) * saiken * shigaika
    net_land = (eff_area * micro_man * qual_mult - fixed_sqm * denom).clip(lower=0.0)
    return net_land, qual_mult


def _blend_oof_preserving_parcel_physics(
    df: pd.DataFrame,
    base: pd.Series,
    oof: pd.Series,
    property_type: str,
    qual_mult: np.ndarray,
    denom: pd.Series,
) -> pd.Series:
    oof_lin = np.clip(np.expm1(oof.to_numpy(dtype=float)), 0.0, None)
    fixed_sqm = _col_series(df, "fixed_cost_per_sqm", 0.0).to_numpy(dtype=float)

    if property_type == "tochi":
        eff_ratio = (_col_series(df, "effective_tochi_menseki", denom) / denom).to_numpy(dtype=float)
        adj_unit = np.clip(oof_lin * np.clip((eff_ratio * qual_mult) / 0.95, 0.15, 2.50) - fixed_sqm, 0.02, None)
        oof_adj = np.log1p(adj_unit)
    elif property_type in ("kodate", "apartment"):
        std_lot = 1.15 if property_type == "kodate" else 0.65
        lot_ratio = _col_series(df, "lot_to_building_ratio", std_lot).to_numpy(dtype=float)
        land_share = _col_series(df, "land_value_share", 0.60 if property_type == "kodate" else 0.45).to_numpy(dtype=float)
        lot_adj = np.clip((lot_ratio / std_lot) * qual_mult, 0.20, 3.00)
        prop_mult = (1.0 - land_share) + land_share * lot_adj
        adj_unit = np.clip(oof_lin * prop_mult - fixed_sqm, 0.05, None)
        oof_adj = np.log1p(adj_unit)
    else:
        oof_adj = oof.to_numpy(dtype=float)

    blended = np.where(oof.to_numpy(dtype=float) > 0.05, 0.55 * oof_adj + 0.45 * base.to_numpy(dtype=float), base.to_numpy(dtype=float))
    return pd.Series(blended, index=df.index, dtype=float)


def refresh_anchor_log_unit_price_column(df: pd.DataFrame, property_type: str = "") -> pd.Series:
    """
    学習・推論時の DataFrame 上で `micro_land_price` や `chome_oof_unit_price` が更新された際、
    敷地レバレッジ・物理減価・固定費控除を保持したまま `anchor_log_unit_price` を再計算する。
    """
    base = _col_series(df, "anchor_log_unit_price", 0.0)
    denom = _col_series(df, "area", 100.0).clip(lower=1.0)
    qual_mult = np.ones(len(df), dtype=float)

    if property_type in ("tochi", "kodate", "apartment") and "micro_land_price" in df.columns and "area" in df.columns:
        net_land, qual_mult = _vectorized_net_land_man(df, property_type, denom)
        bldg_man = _col_series(df, "bldg_component_man", 0.0).clip(lower=0.0)
        if property_type == "tochi":
            base = pd.Series(np.log1p((net_land / denom).clip(lower=0.02)), index=df.index, dtype=float)
        elif property_type == "kodate":
            phys_unit = ((net_land + bldg_man) / denom).clip(lower=0.05)
            base = pd.Series(np.log1p(phys_unit), index=df.index, dtype=float)
        else:
            phys_tot = net_land + bldg_man
            dcf_tot = _col_series(df, "dcf_theoretical_value", phys_tot)
            dep = _col_series(df, "building_depreciation_ratio", 0.5).clip(lower=0.0, upper=1.0)
            w_p = (0.35 + 0.45 * (1.0 - dep)).clip(lower=0.35, upper=0.80)
            apt_tot = np.maximum(w_p * phys_tot + (1.0 - w_p) * dcf_tot, net_land * 0.92)
            base = pd.Series(np.log1p((apt_tot / denom).clip(lower=0.05)), index=df.index, dtype=float)

    if "chome_oof_unit_price" in df.columns:
        oof = _col_series(df, "chome_oof_unit_price", 0.0)
        base = _blend_oof_preserving_parcel_physics(df, base, oof, property_type, qual_mult, denom)
    return base


def _compute_demolition_man(
    property_type: str,
    furuya_cost: float,
    tatemono_area: float,
    chikunen: float,
    is_saikenchiku_fuka: float,
    building_depreciation_ratio: float,
) -> float:
    if property_type == "mansion" or is_saikenchiku_fuka >= 0.5:
        return 0.0
    if property_type == "tochi":
        return float(furuya_cost)
    if tatemono_area <= 0:
        return 0.0
    if chikunen >= 35.0 or building_depreciation_ratio <= 0.05:
        return round(tatemono_area * 1.4, 2)
    return 0.0


def _resolve_bldg_component_man(ctx: LandValuationContext, demolish_man: float) -> float:
    if ctx.property_type == "tochi":
        return 0.0
    if demolish_man > 0.0 and ctx.is_saikenchiku_fuka < 0.5:
        return 0.0
    land_man_unit = float(ctx.micro_land_price) / 10000.0
    if ctx.property_type == "mansion":
        unadj_land = (max(1.0, ctx.gross_area) * 0.20) * land_man_unit * ctx.rights_ratio
    else:
        unadj_land = max(0.0, ctx.effective_tochi_area) * land_man_unit * ctx.scale_discount * ctx.rights_ratio
    return round(max(0.0, float(ctx.cost_approach_value) - unadj_land), 2)


def extract_land_valuation_extras(ctx: LandValuationContext) -> dict[str, float]:
    """全物件種別に共通および土地構成要素（土地・戸建て・アパート・マンション敷地権）の評価特徴量を一括生成する。"""
    norm_text = unicodedata.normalize("NFKC", ctx.combined_text or "")
    dem_feat = lookup_cached_dem_features(ctx.latitude, ctx.longitude)
    tx_hit = lookup_transaction_benchmark(ctx.address1, ctx.address2, ctx.chome_group, ctx.property_type)

    infra_score, infra_cost = _evaluate_infra_connection(norm_text, ctx.chome_infra_score)
    elev_m = _extract_elevation_diff_m(ctx.property_obj, norm_text, dem_slope_deg=dem_feat.dem_slope_deg)
    wall_ref_area = ctx.gross_area if ctx.property_type == "tochi" else ctx.effective_tochi_area
    wall_cost = _estimate_retaining_wall_cost(norm_text, elev_m, wall_ref_area)

    demolish_man = _compute_demolition_man(
        ctx.property_type,
        ctx.furuya_demolition_cost,
        ctx.tatemono_area,
        ctx.chikunen,
        ctx.is_saikenchiku_fuka,
        ctx.building_depreciation_ratio,
    )
    if ctx.property_type == "mansion":
        infra_cost = 0.0
        wall_cost = 0.0

    fixed_total = round(demolish_man + infra_cost + wall_cost, 2)
    denom_sqm = max(1.0, float(ctx.gross_area if ctx.gross_area > 0 else max(10.0, ctx.effective_tochi_area)))
    fixed_per_sqm = round(fixed_total / max(10.0, denom_sqm), 4) if fixed_total > 0 else 0.0

    is_measured = (
        1.0 if (any(k in norm_text for k in _MEASURED_BOUNDARY_KW) and "境界非明示" not in norm_text) else 0.0
    )
    is_cul_de_sac = 1.0 if any(k in norm_text for k in _CUL_DE_SAC_KW) else 0.0
    is_special_share = _detect_special_sale_share(norm_text)

    has_land_component = ctx.property_type in ("tochi", "kodate", "apartment")
    subdiv_score = (
        _calculate_subdivision_potential(
            ctx.effective_tochi_area,
            ctx.maguchi_val,
            ctx.road_width_val,
            ctx.is_saikenchiku_fuka,
            ctx.is_shigaika_chousei,
        )
        if has_land_component
        else 0.0
    )

    dcf_val = _compute_dcf_safe(ctx.property_obj, ctx.property_type)
    kodate_res_land = (
        _compute_kodate_residual_land_value(
            ctx.mkt_comparison_master,
            ctx.address1,
            ctx.address2,
            ctx.effective_tochi_area,
            float(ctx.micro_land_price),
            ctx.scale_discount,
            ctx.road_condition_factor,
            ctx.frontage_penalty_factor,
            fixed_total,
        )
        if has_land_component
        else 0.0
    )

    bldg_comp_man = _resolve_bldg_component_man(ctx, demolish_man)
    if ctx.property_type == "mansion":
        lot_bldg_ratio = 0.20
    elif ctx.property_type == "tochi":
        lot_bldg_ratio = round(max(0.0, ctx.effective_tochi_area) / denom_sqm, 4)
    else:
        lot_bldg_ratio = round(max(0.0, ctx.effective_tochi_area) / denom_sqm, 4)

    anchor_inp = AnchorPricingInput(
        property_type=ctx.property_type,
        gross_area=denom_sqm,
        effective_tochi_area=ctx.effective_tochi_area,
        micro_land_price=float(ctx.micro_land_price),
        scale_discount=ctx.scale_discount,
        frontage_penalty_factor=ctx.frontage_penalty_factor,
        road_condition_factor=ctx.road_condition_factor,
        plot_shape_penalty=ctx.plot_shape_penalty,
        rights_ratio=ctx.rights_ratio,
        is_saikenchiku_fuka=ctx.is_saikenchiku_fuka,
        is_shigaika_chousei=ctx.is_shigaika_chousei,
        fixed_cost_per_sqm=fixed_per_sqm,
        cost_approach_value=ctx.cost_approach_value,
        income_approach_value=ctx.income_approach_value,
        dcf_theoretical_value=dcf_val,
        mkt_comparison_value=ctx.mkt_comparison_value,
        bldg_component_man=bldg_comp_man,
        building_depreciation_ratio=ctx.building_depreciation_ratio,
        mlit_tx_unit_price_man=tx_hit.tx_unit_price_man,
        dem_south_aspect_score=dem_feat.dem_south_aspect_score,
        dem_depression_depth_m=dem_feat.dem_depression_depth_m,
    )
    net_land_man = round(_compute_net_land_from_input(anchor_inp), 2)
    net_land_sqm = round(net_land_man / denom_sqm, 4)
    land_share = round(net_land_man / max(1.0, net_land_man + bldg_comp_man), 4)
    anchor_log = compute_anchor_log_unit_price(anchor_inp)

    muni_denom = max(1.0, float(ctx.average_land_price))
    micro_ratio = round(float(ctx.micro_land_price) / muni_denom, 4)
    default_oof = anchor_log

    return {
        "micro_land_price": float(ctx.micro_land_price),
        "micro_to_muni_land_ratio": micro_ratio,
        "chome_infra_score": float(ctx.chome_infra_score),
        "dem_elevation_m": dem_feat.dem_elevation_m,
        "dem_slope_deg": dem_feat.dem_slope_deg,
        "dem_south_aspect_score": dem_feat.dem_south_aspect_score,
        "dem_depression_depth_m": dem_feat.dem_depression_depth_m,
        "mlit_tx_unit_price_man": tx_hit.tx_unit_price_man,
        "asking_to_tx_spread_ratio": tx_hit.asking_to_tx_spread_ratio,
        "lot_to_building_ratio": lot_bldg_ratio,
        "net_land_component_man": net_land_man,
        "bldg_component_man": bldg_comp_man,
        "net_land_per_sqm": net_land_sqm,
        "land_value_share": land_share,
        "infra_connection_score": infra_score,
        "estimated_infra_cost_man": infra_cost,
        "elevation_diff_m": elev_m,
        "retaining_wall_cost_man": wall_cost,
        "estimated_fixed_cost_man": fixed_total,
        "fixed_cost_per_sqm": fixed_per_sqm,
        "is_measured_boundary": is_measured,
        "is_cul_de_sac_road": is_cul_de_sac,
        "is_special_sale_share": is_special_share,
        "subdivision_potential_score": subdiv_score,
        "dcf_theoretical_value": dcf_val,
        "kodate_residual_land_value": kodate_res_land,
        "chome_oof_unit_price": default_oof,
        "station_walk_oof_unit_price": default_oof,
        "anchor_log_unit_price": anchor_log,
    }
