"""
ML 再建築不可・権利関係・古家付き土地評価モジュール (Issue #713, Epic #710)
"""
import re
from typing import Any

from package.ml.features.parsers import safe_float


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


_COMBINED_TEXT_ATTRS: tuple[str, ...] = (
    'raw_html', 'rawHtml', 'detail_html', 'page_html',
    'tochikenri', 'biko', 'kuiki', 'urbanPlanning', 'cityPlanning', 'toshiKeikaku',
    'youtoChiiki', 'chimoku', 'chimokuChisei', 'propertyName', 'setsudou', 'roadStructure', 'douro',
    'notes', 'bikou', 'remarks', 'note', 'genkyo', 'currentStatus', 'kenchikuJoken',
    'chisei', 'boukaChiiki', 'chiikiChiku', 'saikenchiku',
    'setsubi', 'equipment', 'facilities', 'gas', 'suidou', 'gesui', 'sokuryo',
)

_SHIGAIKA_KEYWORDS: tuple[str, ...] = ("市街化調整", "調整区域")
_TERM_SAIKENCHIKU_FUKA = "再建築不可"
_SHINSHAKU_ZERO_KEYWORDS: tuple[str, ...] = (
    "既存宅地",
    "開発許可済",
    "開発許可番号",
    "検査済証",
    "34条11号",
    "34条12号",
    "３４条１１号",
    "３４条１２号",
    "誰でも建築可",
    "どなたでも建築可",
    "どなたでも住宅建築可",
    "一般住宅建築可",
    "宅地並み",
    "郊外型店舗が並ぶ",
    "分譲地内",
)
_SHINSHAKU_THIRTY_KEYWORDS: tuple[str, ...] = (
    "店舗可",
    "事務所可",
    "店舗・事務所",
    "店舗事務所",
    "沿道サービス",
    "幹線道路",
    "国道",
    "県道",
    "バイパス",
    "ロードサイド",
    "34条1号",
    "34条9号",
    "３４条１号",
    "３４条９号",
)
_UNBUILDABLE_STRICT_KEYWORDS: tuple[str, ...] = (
    _TERM_SAIKENCHIKU_FUKA,
    "建築不可",
    "原則建築不可",
    "建築制限",
)
_FARMLAND_TOKENS: tuple[str, ...] = ("田", "畑", "農地", "純農地")
_ZASSHU_TOKENS: tuple[str, ...] = ("雑種", "資材置場", "資材置き場", "車両置場")


def _build_shigaika_inspection_text(property_obj: Any, combined_text: str) -> str:
    text = combined_text or (extract_combined_text_for_prop(property_obj) if property_obj is not None else "")
    if property_obj is None:
        return text
    kuiki_parts = [
        str(_get_attr(property_obj, k, "") or "")
        for k in ("kuiki", "urbanPlanning", "cityPlanning", "toshiKeikaku", "youtoChiiki")
    ]
    return f"{' '.join(p for p in kuiki_parts if p)} {text}".strip()


def _resolve_road_width_for_shinshaku(property_obj: Any, road_width_val: float) -> float:
    rw = safe_float(road_width_val, None)
    if rw is None and property_obj is not None:
        rw = safe_float(_get_attr(property_obj, "roadWidth", _get_attr(property_obj, "douroHaba", 4.0)), 4.0)
    return float(rw or 4.0)


def resolve_shigaika_shinshaku_rate(
    property_obj: Any = None,
    combined_text: str = "",
    road_width_val: float = 4.0,
) -> tuple[float, float]:
    """
    市街化調整区域の該当有無と「しんしゃく割合（斟酌割合: 0.0 / 0.30 / 0.50）」を判定する (Issue #1370)。

    Returns:
        (is_shigaika_chousei, shinshaku_rate)
        - 建築不可・原則利用制限がある土地: 50%減 (shinshaku_rate = 0.50)
        - 店舗・事務所などの建築が可能な幹線道路沿いなど: 30%減 (shinshaku_rate = 0.30)
        - 郊外型店舗が並ぶ・既存宅地・開発許可済・34条11号/12号など宅地と同等の取引実態がある地域: 0%減 (shinshaku_rate = 0.00)
    """
    text = _build_shigaika_inspection_text(property_obj, combined_text)
    if not any(k in text for k in _SHIGAIKA_KEYWORDS):
        return 0.0, 0.0

    if any(k in text for k in _UNBUILDABLE_STRICT_KEYWORDS):
        return 1.0, 0.50

    if any(k in text for k in _SHINSHAKU_ZERO_KEYWORDS):
        return 1.0, 0.0

    rw_val = _resolve_road_width_for_shinshaku(property_obj, road_width_val)
    if any(k in text for k in _SHINSHAKU_THIRTY_KEYWORDS) or (
        rw_val >= 6.0 and any(k in text for k in ("店舗", "事務所", "商業", "事業用"))
    ):
        return 1.0, 0.30

    return 1.0, 0.50


def compute_shigaika_land_unit_price(
    nearby_standard_price: float,
    estimated_fixed_asset_price: float | None = None,
    plot_adjustment_factor: float = 1.0,
    shinshaku_rate: float = 0.50,
    takuchi_bairitsu: float = 1.10,
) -> float:
    """
    市街化調整区域の宅地評価における2方式比較（低い方の金額を採用） (Issue #1370):
      1. 固定資産税評価額 × 宅地倍率
      2. 近傍標準宅地の単価（または路線価）× 宅地倍率 × 画地調整率 × (1 - しんしゃく割合)
    """
    base_price = max(1.0, float(nearby_standard_price))
    fixed_asset = (
        float(estimated_fixed_asset_price)
        if (estimated_fixed_asset_price is not None and float(estimated_fixed_asset_price) > 0)
        else base_price * 0.70
    )
    bairitsu = max(0.5, float(takuchi_bairitsu))
    plot_adj = min(1.20, max(0.20, float(plot_adjustment_factor)))
    shinshaku = min(0.80, max(0.0, float(shinshaku_rate)))

    method1_price = fixed_asset * bairitsu
    method2_price = base_price * bairitsu * plot_adj * (1.0 - shinshaku)
    return round(min(method1_price, method2_price), 2)


def _resolve_farmland_multiplier(c: str, in_chousei: bool, shinshaku: float) -> float | None:
    if "純農地" in c or (in_chousei and any(k in c for k in _FARMLAND_TOKENS)):
        base_farm = 0.28 if "田" in c else 0.35
        return round(base_farm * max(0.60, 1.0 - shinshaku * 0.5), 4)
    if "田" in c or "農地" in c:
        return 0.63
    if "畑" in c:
        return 0.85
    return None


def resolve_chimoku_valuation_multiplier(
    chimoku_str: str = "",
    is_shigaika_chousei: float = 0.0,
    shinshaku_rate: float = 0.0,
    combined_text: str = "",
) -> float:
    """
    地目（宅地・雑種地・農地［田・畑］・山林・原野）および利用制限に応じた評価比準倍率を返す (Issue #1370)。
    - 雑種地（資材置き場や駐車場など）：近傍宅地比準 × 利用制限しんしゃく減価
    - 農地（田・畑）：純農地（調整区域農地）は農地比準、市街化区域内農地は宅地比準から造成・転用費控除
    """
    c = f"{chimoku_str or ''} {combined_text or ''}".strip()
    in_chousei = float(is_shigaika_chousei) >= 0.5
    shinshaku = min(0.80, max(0.0, float(shinshaku_rate)))

    farm_mult = _resolve_farmland_multiplier(c, in_chousei, shinshaku)
    if farm_mult is not None:
        return farm_mult
    if "山林" in c:
        return 0.40 if in_chousei else 0.68
    if "原野" in c:
        return 0.35 if in_chousei else 0.77
    if any(k in c for k in _ZASSHU_TOKENS):
        return round(0.85 * (1.0 - max(0.30, shinshaku)), 4) if in_chousei else 0.90
    return 1.0


def _compute_shigaika_base_multiplier(
    property_type: str,
    combined_text: str,
    nearby_standard_price: float,
    estimated_fixed_asset_price: float | None,
    shinshaku_rate: float,
) -> float:
    base_lp = max(1.0, float(nearby_standard_price))
    eff_fixed_asset = (
        max(float(estimated_fixed_asset_price), base_lp * 0.70)
        if (estimated_fixed_asset_price is not None and float(estimated_fixed_asset_price) > 0)
        else base_lp * 0.70
    )
    min_unit_std = compute_shigaika_land_unit_price(
        nearby_standard_price=base_lp * 0.80,
        estimated_fixed_asset_price=eff_fixed_asset,
        plot_adjustment_factor=1.0,
        shinshaku_rate=shinshaku_rate,
        takuchi_bairitsu=1.10,
    )
    shigaika_mult = min_unit_std / base_lp
    if property_type == "tochi" and shinshaku_rate >= 0.50 and _TERM_SAIKENCHIKU_FUKA in (combined_text or ""):
        return min(shigaika_mult, 0.35)
    return shigaika_mult


def _combine_shigaika_and_chimoku_multiplier(
    is_shigaika: float,
    shigaika_mult: float,
    shinshaku_rate: float,
    chimoku_val: str,
    combined_text: str,
) -> float:
    merged_text = f"{chimoku_val} {combined_text}"
    if is_shigaika >= 0.5 and any(k in merged_text for k in _ZASSHU_TOKENS):
        chimoku_mult = 0.85
    elif is_shigaika >= 0.5 and any(k in merged_text for k in _FARMLAND_TOKENS):
        chimoku_mult = resolve_chimoku_valuation_multiplier(
            chimoku_val, is_shigaika_chousei=1.0, shinshaku_rate=shinshaku_rate, combined_text=combined_text
        ) / max(0.10, shigaika_mult)
    else:
        chimoku_mult = resolve_chimoku_valuation_multiplier(
            chimoku_val, is_shigaika_chousei=is_shigaika, shinshaku_rate=shinshaku_rate, combined_text=combined_text
        )
    return round(min(1.0, max(0.10, shigaika_mult * chimoku_mult)), 4)


def resolve_effective_land_price_multiplier(
    property_obj: Any = None,
    property_type: str = "tochi",
    combined_text: str = "",
    chimoku_str: str = "",
    road_width_val: float = 4.0,
    nearby_standard_price: float = 100_000.0,
    estimated_fixed_asset_price: float | None = None,
) -> tuple[float, float, float]:
    """
    (is_shigaika_chousei, shinshaku_rate, effective_land_multiplier) を一括解決する。
    市街化調整区域の場合は倍率方式（方式①）と近傍宅地比準×(1-しんしゃく割合)（方式②）の min から実効乗数を算出し、
    さらに雑種地・農地（田・畑）の比準倍率を合成する。
    """
    is_shigaika, shinshaku_rate = resolve_shigaika_shinshaku_rate(
        property_obj=property_obj, combined_text=combined_text, road_width_val=road_width_val
    )
    chimoku_val = chimoku_str or (
        str(_get_attr(property_obj, "chimoku", _get_attr(property_obj, "chimokuChisei", "")) or "")
        if property_obj is not None
        else ""
    )
    shigaika_mult = (
        _compute_shigaika_base_multiplier(
            property_type, combined_text, nearby_standard_price, estimated_fixed_asset_price, shinshaku_rate
        )
        if is_shigaika >= 0.5
        else 1.0
    )
    eff_mult = _combine_shigaika_and_chimoku_multiplier(
        is_shigaika, shigaika_mult, shinshaku_rate, chimoku_val, combined_text
    )
    return is_shigaika, shinshaku_rate, eff_mult


def extract_combined_text_for_prop(property_obj: Any) -> str:
    parts = [str(_get_attr(property_obj, attr, '') or '') for attr in _COMBINED_TEXT_ATTRS]
    return " ".join(p for p in parts if p)


def _determine_demolish_unit(combined_text: str) -> float:
    if "鉄骨" in combined_text:
        return 1.8
    if any(x in combined_text for x in ["RC", "鉄筋"]):
        return 2.5
    return 1.4


def _calculate_furuya_values(
    furuya_bldg_area: float,
    average_land_price: float,
    tochi_area: float,
    scale_discount: float,
    is_saikenchiku_fuka: float,
    furuya_demolition_cost: float
) -> tuple[float, float]:
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
    cost_approach_value: float,
    income_approach_value: float,
    residual_land_value: float,
    is_saikenchiku_fuka: float,
    furuya_usable_value: float,
    furuya_demolition_cost: float,
    furuya_option_value: float
) -> tuple[float, float, float]:
    if is_saikenchiku_fuka >= 0.5:
        c_val = furuya_usable_value
        i_val = max(income_approach_value, furuya_usable_value)
    else:
        c_val = max(0.0, cost_approach_value - furuya_demolition_cost) + (furuya_option_value * 0.5)
        i_val = max(income_approach_value, furuya_usable_value) if furuya_usable_value > 0 else income_approach_value
    r_val = max(0.0, residual_land_value - furuya_demolition_cost) if furuya_demolition_cost > 0 else residual_land_value
    return c_val, i_val, r_val


def evaluate_furuya(
    combined_text: str,
    property_type: str,
    tochi_area: float,
    tatemono_area: float,
    average_land_price: float,
    scale_discount: float,
    is_saikenchiku_fuka: float,
    cost_approach_value: float,
    income_approach_value: float,
    residual_land_value: float
) -> dict[str, float]:
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


def _apply_land_legal_and_chimoku_adjustments(
    property_type: str,
    tochi_area: float,
    average_land_price: float,
    scale_discount: float,
    cost_approach_value: float,
    residual_land_value: float,
    eff_land_mult: float,
) -> tuple[float, float]:
    if eff_land_mult >= 0.9999 or property_type == "mansion":
        return cost_approach_value, residual_land_value

    raw_land_val = max(0.0, tochi_area * (average_land_price / 10000.0) * scale_discount)
    if property_type == "tochi":
        adj_cost = round(cost_approach_value * eff_land_mult, 2)
    else:
        bldg_part = max(0.0, cost_approach_value - raw_land_val)
        adj_cost = round(raw_land_val * eff_land_mult + bldg_part, 2)
    adj_res = round(residual_land_value * eff_land_mult, 2)
    return adj_cost, adj_res


def extract_legal_and_furuya_features(
    property_type: str,
    combined_text: str,
    chikunen: float,
    tochi_area: float,
    tatemono_area: float,
    average_land_price: float,
    scale_discount: float,
    cost_approach_value: float,
    income_approach_value: float,
    residual_land_value: float,
    property_obj: Any = None,
    estimated_fixed_asset_price: float | None = None,
) -> dict[str, float]:
    combined_text_lower = combined_text.lower()
    unbuildable_keywords = (
        _TERM_SAIKENCHIKU_FUKA,
        "建築基準法に定める道路に接していない",
        "再建築時には建築審査会の同意",
        "建築審査会の同意を得て",
    )
    is_saikenchiku_fuka = 1.0 if any(k in combined_text for k in unbuildable_keywords) else 0.0
    chimoku_str = (
        str(_get_attr(property_obj, "chimoku", _get_attr(property_obj, "chimokuChisei", "")) or "")
        if property_obj is not None
        else ""
    )
    road_width_val = _resolve_road_width_for_shinshaku(property_obj, 4.0)

    is_shigaika_chousei, shinshaku_rate, eff_land_mult = resolve_effective_land_price_multiplier(
        property_obj=property_obj,
        property_type=property_type,
        combined_text=combined_text,
        chimoku_str=chimoku_str,
        road_width_val=road_width_val,
        nearby_standard_price=average_land_price,
        estimated_fixed_asset_price=estimated_fixed_asset_price,
    )
    cost_approach_value, residual_land_value = _apply_land_legal_and_chimoku_adjustments(
        property_type,
        tochi_area,
        average_land_price,
        scale_discount,
        cost_approach_value,
        residual_land_value,
        eff_land_mult,
    )

    sokochi_keywords = (
        "底地",
        "貸地",
        "借地権が設定されている土地",
        "借地権（賃借権）が設定されている土地",
        "借地権(賃借権)が設定されている土地",
        "徴収する地代",
    )
    rights_ratio = 1.0
    if any(k in combined_text_lower for k in sokochi_keywords):
        rights_ratio = 0.20
    elif "定期" in combined_text_lower or "定借" in combined_text_lower:
        remaining_ratio = max(0.20, (50 - chikunen) / 50.0) if chikunen > 0 else 0.50
        rights_ratio = 0.70 * remaining_ratio
    elif "借地" in combined_text_lower or "賃借" in combined_text_lower:
        rights_ratio = 0.65

    res = evaluate_furuya(
        combined_text, property_type, tochi_area, tatemono_area, average_land_price * eff_land_mult, scale_discount,
        is_saikenchiku_fuka, cost_approach_value, income_approach_value, residual_land_value
    )
    res["is_shigaika_chousei"] = is_shigaika_chousei
    res["shigaika_shinshaku_rate"] = shinshaku_rate
    res["effective_land_price_multiplier"] = eff_land_mult
    res["is_saikenchiku_fuka"] = is_saikenchiku_fuka
    res["rights_ratio"] = rights_ratio
    return res


# Backward compatibility aliases
_extract_combined_text_for_prop = extract_combined_text_for_prop
_evaluate_furuya = evaluate_furuya
_extract_legal_and_furuya_features = extract_legal_and_furuya_features
