# -*- coding: utf-8 -*-
"""Issue #922: Auto-Heal 単価上限引上げ・面積抽出フォールバック・残留不整合レコード同期のテスト"""
from types import SimpleNamespace


from package.utils.data_validator import (
    PropertyDataValidator,
)


def test_unit_price_up_to_50m_yen_allowed():
    """都心高額物件（虎ノ門31.5億円等）で平米単価が1500万超5000万円以下の場合は単価異常とならないこと"""
    item = SimpleNamespace(
        propertyName="虎ノ門5丁目 土地",
        address="東京都港区虎ノ門5丁目",
        traffic="神谷町駅 徒歩3分",
        price=3150000000,  # 31.5億円
        tochiMenseki=128.69,  # 単価約2,448万円/㎡
    )
    ok, reasons = PropertyDataValidator.validate_property(item, "tochi")
    assert ok, reasons
    assert not any("単価異常" in r for r in reasons)


def test_unit_price_over_50m_yen_flagged():
    """平米単価が5000万円/㎡を超える極大値は単価異常として検知されること"""
    item = SimpleNamespace(
        propertyName="超高額物件",
        address="東京都中央区銀座",
        traffic="銀座駅 徒歩1分",
        price=3000000000,  # 30億円
        tochiMenseki=50.0,  # 単価6,000万円/㎡
    )
    ok, reasons = PropertyDataValidator.validate_property(item, "tochi")
    assert not ok
    assert any("5000万円/㎡超" in r for r in reasons)


def test_area_fallback_to_valid_candidate_when_first_candidate_is_dummy():
    """建物面積がダミー（例: 1.0㎡）でも土地面積が正常（例: 91.77㎡）ならフォールバックして正常判定されること"""
    item = SimpleNamespace(
        propertyName="矢向 一棟アパート",
        address="神奈川県川崎市幸区小向西町",
        traffic="矢向駅 徒歩20分",
        price=48000000,
        tatemonoMenseki=1.0,  # ダミー値
        tochiMenseki=91.77,  # 有効な土地面積
        grossYield=7.18,
    )
    ok, reasons = PropertyDataValidator.validate_property(item, "investment_apartment")
    assert ok, reasons
    assert not any("面積異常" in r for r in reasons)


def test_area_fails_when_all_candidates_are_under_threshold():
    """専有・建物・土地の全候補が5㎡以下の場合は面積異常となること"""
    item = SimpleNamespace(
        propertyName="極小面積物件",
        address="東京都世田谷区",
        traffic="三軒茶屋駅 徒歩5分",
        price=20000000,
        senyuMenseki=2.0,
        tatemonoMenseki=1.0,
        tochiMenseki=3.0,
    )
    ok, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert not ok
    assert any("5㎡以下" in r for r in reasons)


def test_scan_anomalies_resolves_valid_property_evaluations():
    """auto_heal_parsers のスキャンにおいて、現行バリデータを通過する物件の不整合フラグが解消されること"""
    saved_fields = []

    class MockEval:
        needs_parser_fix = True
        data_quality_issue = "必須項目欠損 (間取りが未抽出)"
        company = "mitsui"
        property_type = "tochi"
        property_id = 123

        def save(self, update_fields=None):
            saved_fields.append(list(update_fields or []))

    mock_ev = MockEval()
    mock_prop = SimpleNamespace(
        id=123,
        propertyName="正常土地",
        address="東京都港区",
        traffic="駅 徒歩5分",
        price=50000000,
        tochiMenseki=100.0,
    )

    is_valid, _reasons = PropertyDataValidator.validate_property(mock_prop, mock_ev.property_type)
    assert is_valid

    if is_valid and (mock_ev.needs_parser_fix or mock_ev.data_quality_issue):
        mock_ev.needs_parser_fix = False
        mock_ev.data_quality_issue = ""
        mock_ev.save(update_fields=["needs_parser_fix", "data_quality_issue"])

    assert mock_ev.needs_parser_fix is False
    assert mock_ev.data_quality_issue == ""
    assert "needs_parser_fix" in saved_fields[0]
    assert "data_quality_issue" in saved_fields[0]

