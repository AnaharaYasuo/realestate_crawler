# -*- coding: utf-8 -*-
"""
テキストスクレイピング解析によるプロ目線リスク抽出テスト (test_text_risk_analyzer.py)
"""
from package.utils.text_risk_analyzer import analyze_text_risks


def test_empty_input():
    res = analyze_text_risks("")
    assert res["is_psychological_defect"] is False
    assert res["is_as_is_condition"] is False
    assert res["is_boundary_unspecified"] is False
    assert res["is_unbuildable"] is False
    assert res["is_urbanization_control_area"] is False
    assert res["has_private_road_burden"] is False
    assert res["is_sublease"] is False
    assert res["gas_type"] == "unknown"
    assert res["sewage_type"] == "unknown"
    assert res["bath_type"] == "unknown"
    assert res["has_elevator"] is None
    assert res["is_stair_only_3f_plus"] is None
    assert res["is_old_earthquake_standard"] is None


def test_psychological_defect_detection():
    # 心理的瑕疵・告知事項
    res1 = analyze_text_risks("閑静な住宅街ですが、本物件は告知事項ありとなります。詳細はお問い合わせください。")
    assert res1["is_psychological_defect"] is True

    res2 = analyze_text_risks("南向き陽当たり良好。駅徒歩5分の好立地。")
    assert res2["is_psychological_defect"] is False


def test_as_is_condition_detection():
    # 契約不適合責任免責・現況有姿
    res1 = analyze_text_risks("売主契約不適合責任免責、現況有姿引渡しとなります。")
    assert res1["is_as_is_condition"] is True

    res2 = analyze_text_risks("瑕疵担保免責での売買となります。")
    assert res2["is_as_is_condition"] is True

    res3 = analyze_text_risks("新築分譲住宅、10年保証付き。")
    assert res3["is_as_is_condition"] is False


def test_unbuildable_detection():
    # 再建築不可・43条但書
    res1 = analyze_text_risks("接道義務を満たしていないため再建築不可。投資用・資材置場等にご検討ください。")
    assert res1["is_unbuildable"] is True

    res2 = analyze_text_risks("建築基準法第43条第2項の許可要件を満たす必要があります（43条但書）。")
    assert res2["is_unbuildable"] is True

    res3 = analyze_text_risks("公道に6m接道した整形地。建築条件なし。")
    assert res3["is_unbuildable"] is False


def test_urbanization_control_area_detection():
    # 市街化調整区域
    res1 = analyze_text_risks("市街化調整区域につき、原則として建物の建築・増改築はできません。")
    assert res1["is_urbanization_control_area"] is True

    res2 = analyze_text_risks("第1種低層住居専用地域。容積率100%。")
    assert res2["is_urbanization_control_area"] is False


def test_private_road_burden_detection():
    # 私道負担・持分なし
    res1 = analyze_text_risks("私道負担あり（持分なし）。前面道路通行掘削承諾書なし。")
    assert res1["has_private_road_burden"] is True

    res2 = analyze_text_risks("公道接道につき私道負担なし。")
    assert res2["has_private_road_burden"] is False

    res3 = analyze_text_risks("私道負担：無")
    assert res3["has_private_road_burden"] is False

    res4 = analyze_text_risks("私道負担あり。持分あり。")
    assert res4["has_private_road_burden"] is True


def test_boundary_unspecified_detection():
    # 境界非明示・公簿売買
    res1 = analyze_text_risks("公簿売買とし、売主による境界非明示、確定測量は行いません。")
    assert res1["is_boundary_unspecified"] is True

    res2 = analyze_text_risks("実測売買、確定測量図面お渡し。")
    assert res2["is_boundary_unspecified"] is False


def test_sublease_detection():
    # サブリース
    res1 = analyze_text_risks("現在サブリース契約中（一括借上中につき解約条件あり）。")
    assert res1["is_sublease"] is True

    res2 = analyze_text_risks("空室につき即入居可能。居住用戸建て。")
    assert res2["is_sublease"] is False


def test_infrastructure_and_bath_detection():
    # 設備・インフラ
    res1 = analyze_text_risks("プロパンガス、単独浄化槽、在来浴室（タイル張り）。")
    assert res1["gas_type"] == "lpg"
    assert res1["sewage_type"] == "purification_tank"
    assert res1["bath_type"] == "tile_traditional"

    res2 = analyze_text_risks("都市ガス、公共下水、公営水道、ユニットバス（1616サイズ）。")
    assert res2["gas_type"] == "city_gas"
    assert res2["sewage_type"] == "public"
    assert res2["bath_type"] == "unit_bath"

    res3 = analyze_text_risks("オール電化住宅、汲取トイレ、仕様設備不明。")
    assert res3["gas_type"] == "all_electric"
    assert res3["sewage_type"] == "cesspool"


def test_old_earthquake_standard_detection():
    # 旧耐震基準 (1981年5月以前)
    res1 = analyze_text_risks("1980年3月築", chikunengetsu_str="1980年3月")
    assert res1["is_old_earthquake_standard"] is True

    res2 = analyze_text_risks("1985年10月築", chikunengetsu_str="1985年10月")
    assert res2["is_old_earthquake_standard"] is False

    res3 = analyze_text_risks("昭和50年4月築", chikunengetsu_str="昭和50年4月")
    assert res3["is_old_earthquake_standard"] is True

    res4 = analyze_text_risks("昭和60年1月築", chikunengetsu_str="昭和60年1月")
    assert res4["is_old_earthquake_standard"] is False


def test_elevator_and_stair_only_detection():
    # エレベーター有無 & 3階以上階段物件
    res1 = analyze_text_risks("オートロック、エレベーター、宅配ボックス完備。所在階4階。", kaisu_str="4階")
    assert res1["has_elevator"] is True
    assert res1["is_stair_only_3f_plus"] is False

    res2 = analyze_text_risks("低層アパート、エレベーターなし、階段利用。所在階3階。", kaisu_str="3階")
    assert res2["has_elevator"] is False
    assert res2["is_stair_only_3f_plus"] is True

    res3 = analyze_text_risks("低層アパート、エレベーターなし、階段利用。所在階2階。", kaisu_str="2階")
    assert res3["has_elevator"] is False
    assert res3["is_stair_only_3f_plus"] is False

    res4 = analyze_text_risks("閑静な住宅街の一戸建て。")
    assert res4["has_elevator"] is None
    assert res4["is_stair_only_3f_plus"] is None

    # エレベーター：無 のコロン区切り形式
    res5 = analyze_text_risks("エレベーター：無 所在階3階", kaisu_str="3階")
    assert res5["has_elevator"] is False
    assert res5["is_stair_only_3f_plus"] is True

    # 所在階なしでも全階数 total_floors=3 で階段3階以上判定
    res6 = analyze_text_risks("エレベーターなし", total_floors=3)
    assert res6["has_elevator"] is False
    assert res6["is_stair_only_3f_plus"] is True


def test_earthquake_boundary_and_false_positives():
    # 境界値テスト: 1981年5月 (True), 1981年6月 (False), 昭和56年5月 (True)
    assert analyze_text_risks(chikunengetsu_str="1981年5月")["is_old_earthquake_standard"] is True
    assert analyze_text_risks(chikunengetsu_str="1981年6月")["is_old_earthquake_standard"] is False
    assert analyze_text_risks(chikunengetsu_str="昭和56年5月")["is_old_earthquake_standard"] is True

    # 偽陽性防止テスト: CLUB は unit_bath にならない
    res_club = analyze_text_risks("近隣にCLUBあり。")
    assert res_club["bath_type"] == "unknown"

    # 偽陽性防止テスト: 契約不適合責任 免責なし は as-is にならない
    res_menseki = analyze_text_risks("契約不適合責任：免責なし。")
    assert res_menseki["is_as_is_condition"] is False

    # 偽陽性防止テスト: 本文中にのみ 2015年リフォーム がある場合は旧耐震を誤判定せず None
    res_reform = analyze_text_risks("2015年リフォーム済み美邸。")
    assert res_reform["is_old_earthquake_standard"] is None

