# -*- coding: utf-8 -*-
"""Issue #922: Auto-Heal 単価上限引上げ・面積抽出フォールバック・残留不整合レコード同期のテスト"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from package.utils.data_validator import (
    PropertyDataValidator,
)
from scripts.debug_tools.auto_heal_parsers import scan_anomalies_and_generate_instructions


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
    """scan_anomalies_and_generate_instructions を呼び出し、正常物件でフラグが解消され、異常物件で理由が抽出されること"""
    saved_fields = []

    class MockValidEval:
        needs_parser_fix = True
        data_quality_issue = "必須項目欠損 (間取りが未抽出)"
        company = "mitsui"
        property_type = "tochi"
        property_id = 101
        analyzed_at = datetime.now(timezone.utc)
        is_published = True

        def save(self, update_fields=None):
            saved_fields.append(list(update_fields or []))

    class MockInvalidEval:
        needs_parser_fix = True
        data_quality_issue = "価格異常"
        company = "mitsui"
        property_type = "tochi"
        property_id = 102
        analyzed_at = datetime.now(timezone.utc)
        is_published = True

        def save(self, update_fields=None):
            pass

    valid_ev = MockValidEval()
    invalid_ev = MockInvalidEval()

    valid_prop = SimpleNamespace(
        id=101,
        propertyName="正常土地",
        address="東京都港区",
        traffic="神谷町駅 徒歩5分",
        price=50000000,
        tochiMenseki=100.0,
        pageUrl="https://example.com/valid",
        priceStr="5,000万円",
        setsudou=None,
    )

    invalid_prop = SimpleNamespace(
        id=102,
        propertyName="異常土地",
        address="東京都港区",
        traffic="神谷町駅 徒歩5分",
        price=0,
        tochiMenseki=100.0,
        pageUrl="https://example.com/invalid",
        priceStr="0円",
        setsudou="南側公道 接面5m",
        maguchi=0,
    )

    mock_model = MagicMock()

    def get_prop(id):
        if id == 101:
            return valid_prop
        elif id == 102:
            return invalid_prop
        raise mock_model.DoesNotExist()

    mock_model.objects.get.side_effect = get_prop
    mock_model.DoesNotExist = Exception

    mock_qs = MagicMock()
    mock_qs.exists.return_value = True
    mock_qs.__iter__.return_value = [valid_ev, invalid_ev]

    recorded_targets = []

    def mock_aggregate(targets, max_targets=50):
        recorded_targets.extend(targets)
        return targets[:max_targets]

    with patch("scripts.debug_tools.auto_heal_parsers.PropertyEvaluation.objects.filter", return_value=mock_qs), \
         patch("scripts.debug_tools.auto_heal_parsers.MODEL_MAP", {("mitsui", "tochi"): mock_model}), \
         patch("scripts.debug_tools.auto_heal_parsers.aggregate_and_sort_targets", side_effect=mock_aggregate), \
         patch("scripts.debug_tools.auto_heal_parsers.summarize_errors_with_gemini", return_value="Gemini summary"), \
         patch("builtins.open", MagicMock()):

        scan_anomalies_and_generate_instructions()

    # 正常物件の不整合フラグが解消されていること
    assert valid_ev.needs_parser_fix is False
    assert valid_ev.data_quality_issue == ""
    assert "needs_parser_fix" in saved_fields[0]
    assert "data_quality_issue" in saved_fields[0]

    # 不合格物件は不整合フラグが維持され、異常ターゲットとして理由が抽出されること
    assert invalid_ev.needs_parser_fix is True
    assert len(recorded_targets) == 1
    assert recorded_targets[0]["url"] == "https://example.com/invalid"
    assert "価格異常" in recorded_targets[0]["reason"]
    assert "間口パース漏れ警告" in recorded_targets[0]["reason"]


def test_mansion_area_does_not_fallback_to_land_area():
    """マンションでは専有面積が5㎡以下の場合、土地面積が存在してもフォールバックせず面積異常となること"""
    item = SimpleNamespace(
        propertyName="テストマンション",
        address="東京都港区",
        traffic="神谷町駅 徒歩3分",
        price=50000000,
        senyuMenseki=1.0,  # 異常値
        tochiMenseki=100.0,
    )
    ok, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert not ok
    assert any("5㎡以下" in r for r in reasons)


