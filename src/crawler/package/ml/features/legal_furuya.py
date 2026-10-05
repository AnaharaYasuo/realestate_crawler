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


def extract_combined_text_for_prop(property_obj: Any) -> str:
    raw_html_content = (
        _get_attr(property_obj, 'raw_html', '')
        or _get_attr(property_obj, 'rawHtml', '')
        or _get_attr(property_obj, 'detail_html', '')
        or _get_attr(property_obj, 'page_html', '')
        or ''
    )
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
    residual_land_value: float
) -> dict[str, float]:
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

    res = evaluate_furuya(
        combined_text, property_type, tochi_area, tatemono_area, average_land_price, scale_discount,
        is_saikenchiku_fuka, cost_approach_value, income_approach_value, residual_land_value
    )
    res["is_shigaika_chousei"] = is_shigaika_chousei
    res["is_saikenchiku_fuka"] = is_saikenchiku_fuka
    res["rights_ratio"] = rights_ratio
    return res


# Backward compatibility aliases
_extract_combined_text_for_prop = extract_combined_text_for_prop
_evaluate_furuya = evaluate_furuya
_extract_legal_and_furuya_features = extract_legal_and_furuya_features
