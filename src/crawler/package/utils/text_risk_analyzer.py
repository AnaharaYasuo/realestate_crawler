"""テキストスクレイピング解析によるプロ買い付け目線リスク抽出モジュール (text_risk_analyzer.py)

物件詳細、備考（biko）、土地権利（tochikenri）、現況（genkyo）、交通（traffic）、設備情報から
ルールベース（正規表現・キーワード検知）により高速・決定論的に各種リスク・設備仕様を抽出する。
"""

import re
from typing import Any


def _extract_legal_risks(raw: str) -> dict[str, bool]:
    """心理的瑕疵、契約免責、境界、再建築、調整区域、私道、サブリース等の権利・法規リスクを抽出する。"""
    is_psychological_defect = bool(re.search(r'告知事項|心理的瑕疵|特別募集|事故物件|訳あり|わけあり', raw))
    is_as_is_condition = bool(
        re.search(r'契約不適合[^\n]{0,10}免責|現況有姿|瑕疵担保免責|瑕疵免責', raw)
        and not re.search(r'免責[：:\s]*(?:なし|無|しない|除外)', raw)
    )
    is_boundary_unspecified = bool(re.search(r'境界非明示|公簿売買|境界未確定|筆界未確定|境界確定なし|確定測量なし', raw))
    is_unbuildable = bool(re.search(r'再建築[^\n]{0,10}不可|建築不可|既存不適格|43条但書|43条2項|接道義務違反|連棟|テラスハウス', raw))
    is_urbanization_control_area = bool(re.search(r'市街化調整区域|調整区域につき', raw))
    has_private_road_burden = bool(
        re.search(r'持分なし|通行掘削承諾[^\n]{0,20}なし|私道持分[^\n]{0,20}なし', raw)
        or (re.search(r'私道負担', raw) and not re.search(r'私道負担[：:\s]*(?:無|なし|ありませ)', raw))
    )
    is_sublease = bool(re.search(r'サブリース|一括借上|賃料保証|家賃保証会社承継', raw))

    return {
        "is_psychological_defect": is_psychological_defect,
        "is_as_is_condition": is_as_is_condition,
        "is_boundary_unspecified": is_boundary_unspecified,
        "is_unbuildable": is_unbuildable,
        "is_urbanization_control_area": is_urbanization_control_area,
        "has_private_road_burden": has_private_road_burden,
        "is_sublease": is_sublease,
    }


def _extract_equipment_specs(raw: str) -> dict[str, str]:
    """ガス、下水、浴室などのインフラ設備仕様を抽出する。"""
    gas_type = "unknown"
    if "オール電化" in raw:
        gas_type = "all_electric"
    elif re.search(r'プロパン|lpg', raw):
        gas_type = "lpg"
    elif re.search(r'都市ガス|本管ガス', raw):
        gas_type = "city_gas"

    sewage_type = "unknown"
    if re.search(r'汲取|汲み取り|くみ取り', raw):
        sewage_type = "cesspool"
    elif re.search(r'浄化槽', raw):
        sewage_type = "purification_tank"
    elif re.search(r'本下水|公共下水|公営下水|下水道', raw):
        sewage_type = "public"

    bath_type = "unknown"
    if re.search(r'ユニットバス|システムバス|\bub\b', raw):
        bath_type = "unit_bath"
    elif re.search(r'在来浴室|在来工法|タイル張', raw):
        bath_type = "tile_traditional"

    return {
        "gas_type": gas_type,
        "sewage_type": sewage_type,
        "bath_type": bath_type,
    }


def _extract_elevator_and_stair(
    raw: str,
    kaisu_str: str | None = None,
    total_floors: int | None = None,
) -> dict[str, bool | None]:
    """エレベーター有無および3階以上階段利用リスクを判定する。"""
    has_elevator = None
    if re.search(r'エレベータ[ー]?[：:\s]*(?:無|なし)|ev[：:\s]*(?:無|なし)', raw):
        has_elevator = False
    elif re.search(r'エレベータ[ー]?|ev[：:\s]*(?:有|あり|完備)', raw):
        has_elevator = True

    floor_num = None
    target_kaisu = f"{kaisu_str or ''} {raw}"
    k_match = re.search(r'([1-9]\d?)\s*(?:階|f)', target_kaisu)
    if k_match:
        floor_num = int(k_match.group(1))

    is_stair_only_3f_plus = None
    if has_elevator is False:
        if (floor_num is not None and floor_num >= 3) or (total_floors is not None and total_floors >= 3):
            is_stair_only_3f_plus = True
        elif floor_num is not None and floor_num < 3:
            is_stair_only_3f_plus = False
    elif has_elevator is True:
        is_stair_only_3f_plus = False

    return {
        "has_elevator": has_elevator,
        "is_stair_only_3f_plus": is_stair_only_3f_plus,
    }


def _extract_earthquake_standard(target_date_str: str) -> bool | None:
    """築年月文字列から旧耐震基準（1981年5月以前）該当有無を判定する。"""
    year_match = re.search(r'(19\d{2}|20\d{2})年(?:(\d{1,2})月)?', target_date_str)
    if year_match:
        year = int(year_match.group(1))
        month = int(year_match.group(2)) if year_match.group(2) else 6
        return year < 1981 or (year == 1981 and month <= 5)

    showa_match = re.search(r'昭和(\d{1,2})年(?:(\d{1,2})月)?', target_date_str)
    if showa_match:
        s_year = int(showa_match.group(1))
        s_month = int(showa_match.group(2)) if showa_match.group(2) else 6
        return s_year < 56 or (s_year == 56 and s_month <= 5)

    return None


def analyze_text_risks(
    text: str = "",
    chikunengetsu_str: str | None = None,
    kaisu_str: str | None = None,
    total_floors: int | None = None,
) -> dict[str, Any]:
    """物件テキスト情報、築年月、階数情報から、プロ目線の権利・法規・設備リスクを判定する。"""
    raw = (text or "").lower()

    legal_risks = _extract_legal_risks(raw)
    equipment_specs = _extract_equipment_specs(raw)
    elevator_specs = _extract_elevator_and_stair(raw, kaisu_str, total_floors)
    earthquake = _extract_earthquake_standard(chikunengetsu_str) if chikunengetsu_str else None

    return {
        **legal_risks,
        **equipment_specs,
        **elevator_specs,
        "is_old_earthquake_standard": earthquake,
    }
