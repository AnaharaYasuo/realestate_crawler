"""
AI課金ゼロの決定論的土地・全種別評価特徴量モジュール (Issue #1360)

- インフラ（上水道・下水・都市ガス）引込スコア・推定引込工事費
- 高低差・擁壁造り替えリスクと推定土木工事費
- 面積非比例の固定費控除総額 (`estimated_fixed_cost_man`)・㎡あたり負担額 (`fixed_cost_per_sqm`)
- 確定測量・袋小路（行き止まり）・共有持分売買フラグ・分筆開発適性スコア
- 10年保有DCF理論価格・戸建て逆算残余地価・アンカー対数単価 (`anchor_log_unit_price`)
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from package.ml.features.parsers import _get_attr, safe_float

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


def _evaluate_infra_connection(norm_text: str, chome_infra_score: float) -> tuple[float, float]:
    if any(k in norm_text for k in _WATER_UNCONNECTED_KW):
        w_score, w_cost = 0.0, 95.0
    else:
        w_score, w_cost = 1.0, 0.0

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


def _extract_elevation_diff_m(property_obj: Any, norm_text: str) -> float:
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
    lots_by_area = effective_tochi_area / 85.0
    lots_by_front = maguchi_val / 4.5
    possible_lots = min(4.0, math.floor(min(lots_by_area, lots_by_front)))
    if possible_lots < 2.0:
        return 0.0
    wide_road_bonus = 0.10 if road_width_val >= 5.0 else 0.0
    return round(min(1.0, (possible_lots - 1.0) * 0.45 + wide_road_bonus), 4)


def _compute_dcf_safe(property_obj: Any, property_type: str) -> float:
    try:
        # Lazy import to avoid circular import when dcf_valuation imports package.ml.features.appraisal
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


def compute_anchor_log_unit_price(inp: AnchorPricingInput) -> float:
    """物件種別に応じた物理・収益・ミクロ地価ベースの理論対数㎡単価 `log1p(万円/㎡)` を算出する。"""
    denom = max(1.0, float(inp.gross_area))
    if inp.property_type == "tochi":
        micro_unit_man = max(0.05, float(inp.micro_land_price) / 10000.0)
        eff_ratio = (
            (max(1.0, float(inp.effective_tochi_area)) / denom)
            * float(inp.scale_discount)
            * float(inp.frontage_penalty_factor)
            * float(inp.road_condition_factor)
            * float(inp.plot_shape_penalty)
            * float(inp.rights_ratio)
            * (0.25 if inp.is_saikenchiku_fuka >= 0.5 else 1.0)
            * (0.35 if inp.is_shigaika_chousei >= 0.5 else 1.0)
        )
        net_unit_man = max(0.02, micro_unit_man * eff_ratio - float(inp.fixed_cost_per_sqm))
        return round(float(math.log1p(net_unit_man)), 6)

    candidates = [
        v
        for v in (inp.cost_approach_value, inp.income_approach_value, inp.dcf_theoretical_value)
        if v and v > 0
    ]
    if not candidates:
        fallback_unit = max(0.05, float(inp.micro_land_price) / 10000.0)
        return round(float(math.log1p(fallback_unit)), 6)
    blended_total = float(sum(candidates) / len(candidates))
    unit_man = max(0.05, (blended_total / denom) - float(inp.fixed_cost_per_sqm) * 0.5)
    return round(float(math.log1p(unit_man)), 6)


def _col_numeric_or_default(df: pd.DataFrame, col: str, default: float | pd.Series) -> pd.Series | float:
    if col not in df.columns:
        return default
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def _col_flag_multiplier(df: pd.DataFrame, col: str, penalty: float) -> np.ndarray | float:
    if col not in df.columns:
        return 1.0
    vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return np.where(vals >= 0.5, penalty, 1.0)


def refresh_anchor_log_unit_price_column(df: pd.DataFrame, property_type: str = "") -> pd.Series:
    """
    学習・推論時の DataFrame 上で `micro_land_price` や `chome_oof_unit_price` が更新された際、
    それらを即座に `anchor_log_unit_price` に反映するベクトル化ヘルパー。
    """
    base_raw = _col_numeric_or_default(df, "anchor_log_unit_price", 0.0)
    base = (
        base_raw.astype(float)
        if isinstance(base_raw, pd.Series)
        else pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    )

    if property_type == "tochi" and "micro_land_price" in df.columns and "area" in df.columns:
        micro_man = (pd.to_numeric(df["micro_land_price"], errors="coerce").fillna(80000.0) / 10000.0).clip(lower=0.05)
        denom = pd.to_numeric(df["area"], errors="coerce").fillna(100.0).clip(lower=1.0)
        eff_series = _col_numeric_or_default(df, "effective_tochi_menseki", denom)
        eff_area = pd.Series(eff_series, index=df.index, dtype=float).clip(lower=1.0)
        scale_d = _col_numeric_or_default(df, "scale_discount", 1.0)
        front_f = _col_numeric_or_default(df, "frontage_penalty_factor", 1.0)
        road_f = _col_numeric_or_default(df, "road_condition_factor", 1.0)
        shape_f = _col_numeric_or_default(df, "plot_shape_penalty", 1.0)
        rights_f = _col_numeric_or_default(df, "rights_ratio", 1.0)
        fixed_sqm = _col_numeric_or_default(df, "fixed_cost_per_sqm", 0.0)
        saiken = _col_flag_multiplier(df, "is_saikenchiku_fuka", 0.25)
        shigaika = _col_flag_multiplier(df, "is_shigaika_chousei", 0.35)
        net_unit = (
            micro_man * (eff_area / denom) * scale_d * front_f * road_f * shape_f * rights_f * saiken * shigaika
            - fixed_sqm
        ).clip(lower=0.02)
        base = pd.Series(np.log1p(net_unit), index=df.index, dtype=float)

    if "chome_oof_unit_price" in df.columns:
        oof = pd.to_numeric(df["chome_oof_unit_price"], errors="coerce").fillna(0.0)
        base = pd.Series(
            np.where(oof > 0.05, 0.55 * oof + 0.45 * base, base),
            index=df.index,
            dtype=float,
        )
    return base


def _compute_demolition_man(property_type: str, furuya_cost: float, tatemono_area: float, chikunen: float) -> float:
    if property_type == "mansion":
        return 0.0
    if property_type == "tochi":
        return float(furuya_cost)
    return round(tatemono_area * 1.4, 2) if chikunen >= 35.0 and tatemono_area > 0 else 0.0


def extract_land_valuation_extras(ctx: LandValuationContext) -> dict[str, float]:
    """全物件種別に共通または土地・戸建てに特化した追加数値特徴量を一括生成する。"""
    norm_text = unicodedata.normalize("NFKC", ctx.combined_text or "")
    infra_score, infra_cost = _evaluate_infra_connection(norm_text, ctx.chome_infra_score)
    elev_m = _extract_elevation_diff_m(ctx.property_obj, norm_text)
    wall_ref_area = ctx.gross_area if ctx.property_type == "tochi" else ctx.effective_tochi_area
    wall_cost = _estimate_retaining_wall_cost(norm_text, elev_m, wall_ref_area)

    demolish_man = _compute_demolition_man(
        ctx.property_type, ctx.furuya_demolition_cost, ctx.tatemono_area, ctx.chikunen
    )
    if ctx.property_type == "mansion":
        infra_cost = 0.0
        wall_cost = 0.0

    fixed_total = round(demolish_man + infra_cost + wall_cost, 2)
    denom_sqm = max(10.0, float(ctx.gross_area if ctx.gross_area > 0 else ctx.effective_tochi_area))
    fixed_per_sqm = round(fixed_total / denom_sqm, 4) if fixed_total > 0 else 0.0

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

    muni_denom = max(1.0, float(ctx.average_land_price))
    micro_ratio = round(float(ctx.micro_land_price) / muni_denom, 4)
    default_oof = round(float(math.log1p(max(0.05, float(ctx.micro_land_price) / 10000.0))), 6)

    anchor_log = compute_anchor_log_unit_price(
        AnchorPricingInput(
            property_type=ctx.property_type,
            gross_area=ctx.gross_area,
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
        )
    )

    return {
        "micro_land_price": float(ctx.micro_land_price),
        "micro_to_muni_land_ratio": micro_ratio,
        "chome_infra_score": float(ctx.chome_infra_score),
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
