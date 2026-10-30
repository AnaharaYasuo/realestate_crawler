# -*- coding: utf-8 -*-
from scripts.ops.send_recommendations import (
    _evaluate_candidate,
    _get_target_slack_channel,
    _select_balanced_recommendations,
)

class MockProperty:
    def __init__(self, pageUrl, price, propertyName="テスト物件"):
        self.pageUrl = pageUrl
        self.price = price
        self.propertyName = propertyName

class MockEvaluation:
    def __init__(self, property_type, investment_score=None, total_investment_score=None, first_stage_predicted_price=None, second_stage_predicted_price=None, property_url="https://example.com/test", id=1):
        self.id = id
        self.property_type = property_type
        self.investment_score = investment_score
        self.total_investment_score = total_investment_score
        self.first_stage_predicted_price = first_stage_predicted_price
        self.second_stage_predicted_price = second_stage_predicted_price
        self.property_url = property_url

def test_evaluate_investment_candidate_by_score():
    """投資スコア（70点以上）による投資物件抽出判定テスト"""
    # 80点以上
    rec1 = MockEvaluation("investmentapartment", investment_score=85.0, total_investment_score=85.0, id=101)
    prop1 = MockProperty(rec1.property_url, 10000000)
    is_rec, reason, priority = _evaluate_candidate(rec1, prop1)
    assert is_rec is True
    assert "85.0点" in reason
    assert priority == 85.0

    # 70点〜79点（引き下げ後の適格判定）
    rec2 = MockEvaluation("investment", investment_score=72.5, total_investment_score=72.5, id=102)
    prop2 = MockProperty(rec2.property_url, 20000000)
    is_rec, reason, priority = _evaluate_candidate(rec2, prop2)
    assert is_rec is True
    assert "72.5点" in reason
    assert priority == 72.5

    # 70点未満かつ予測なし
    rec3 = MockEvaluation("investmentkodate", investment_score=50.0, total_investment_score=50.0, id=103)
    prop3 = MockProperty(rec3.property_url, 5000000)
    is_rec, reason, priority = _evaluate_candidate(rec3, prop3)
    assert is_rec is False

def test_evaluate_investment_candidate_extreme_prediction_gap_rejected():
    """投資スコアが高くても理論予測価格が売出価格の3倍超または1/3未満の極端な異常値の場合は除外されることを検証 (Issue #1116)"""
    # 例: フローラ・国分寺ＡＢ (売出価格 3,560万円 に対し 理論予測価格 174,133万円 -> 約48.9倍)
    rec_flora = MockEvaluation(
        "investmentapartment",
        total_investment_score=100.0,
        first_stage_predicted_price=174133.0,
        id=999
    )
    prop_flora = MockProperty(rec_flora.property_url, 35600000)
    is_rec, reason, priority = _evaluate_candidate(rec_flora, prop_flora)
    assert is_rec is False
    assert reason == ""
    assert priority == 0.0

    # 極端に低い予測値（売出価格 3,000万円 に対し 予測価格 500万円 -> 約0.16倍）
    rec_low = MockEvaluation(
        "investmentapartment",
        total_investment_score=85.0,
        first_stage_predicted_price=500.0,
        id=1000
    )
    prop_low = MockProperty(rec_low.property_url, 30000000)
    is_rec, reason, priority = _evaluate_candidate(rec_low, prop_low)
    assert is_rec is False

def test_evaluate_investment_candidate_by_discount():
    """投資物件でも理論予測価格が存在し、割安度（discount_pct >= 20%）がある場合の判定テスト"""
    # 売出価格 1,500万円、理論予測価格 2,000万円（割安度 25.0%）、投資スコア未設定
    rec = MockEvaluation("investmentapartment", first_stage_predicted_price=2000.0, id=104)
    prop = MockProperty(rec.property_url, 15000000)
    is_rec, reason, priority = _evaluate_candidate(rec, prop)
    assert is_rec is True
    assert "25.0% 割安" in reason
    assert priority >= 70.0  # 投資優先度換算

def test_get_target_slack_channel_investment(monkeypatch):
    """投資用物件のSlackチャンネルルーティング検証"""
    monkeypatch.delenv("SLACK_RECOMMEND_INVEST_APARTMENT", raising=False)
    monkeypatch.delenv("SLACK_RECOMMEND_INVEST_KODATE", raising=False)

    rec_apt = MockEvaluation("investmentapartment", id=105)
    prop = MockProperty("https://example.com/1", 1000)
    assert _get_target_slack_channel(rec_apt, prop, "アパートA") == "goodproperty-invest-apartment"

    rec_kodate = MockEvaluation("investmentkodate", id=106)
    assert _get_target_slack_channel(rec_kodate, prop, "戸建てB") == "goodproperty-invest-kodate"

def test_select_balanced_recommendations():
    """住居系と投資系が適切にバランス配分されて選定されることを検証"""
    candidates = []
    # 住居系 20件
    for i in range(20):
        ev = MockEvaluation("mansion", id=i + 1)
        prop = MockProperty(f"https://example.com/m{i}", 3000)
        candidates.append((30.0 - i, ev, prop, f"mansion-{i}"))

    # 投資系 5件
    for i in range(5):
        ev = MockEvaluation("investmentapartment", id=100 + i)
        prop = MockProperty(f"https://example.com/inv{i}", 1000)
        candidates.append((85.0 - i, ev, prop, f"inv-{i}"))

    top = _select_balanced_recommendations(candidates, quota=15, min_investment_quota=3)
    assert len(top) <= 15
    inv_count = sum(1 for _, ev, _, _ in top if "invest" in ev.property_type or ev.property_type == "apartment")
    assert inv_count >= 3
