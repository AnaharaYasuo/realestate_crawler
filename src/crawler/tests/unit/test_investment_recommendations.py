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
    """投資物件でも理論価格が存在し、割安度（20%〜35%）を満たす場合のみ推奨されることを検証 (Issue #1239)"""
    # 割安度25%（売出1,000万円に対し予測1,333万円）、投資スコア85点
    rec1 = MockEvaluation("investmentapartment", investment_score=85.0, total_investment_score=85.0, first_stage_predicted_price=1333.0, id=101)
    prop1 = MockProperty(rec1.property_url, 10000000)
    is_rec, reason, priority = _evaluate_candidate(rec1, prop1)
    assert is_rec is True
    assert "25.0% 割安" in reason
    assert priority >= 70.0

    # 投資スコアが高くても理論価格が0（未算出）の場合は推奨除外
    rec_zero = MockEvaluation("investment", investment_score=85.0, total_investment_score=85.0, first_stage_predicted_price=0.0, id=102)
    prop2 = MockProperty(rec_zero.property_url, 20000000)
    is_rec, reason, priority = _evaluate_candidate(rec_zero, prop2)
    assert is_rec is False

    # 70点未満かつ割安度なし
    rec3 = MockEvaluation("investmentkodate", investment_score=50.0, total_investment_score=50.0, first_stage_predicted_price=500.0, id=103)
    prop3 = MockProperty(rec3.property_url, 5000000)
    is_rec, reason, priority = _evaluate_candidate(rec3, prop3)
    assert is_rec is False

def test_evaluate_investment_candidate_pred_price_must_exceed_asking_price():
    """利回り・スコアが高くても理論予測価格が売出価格以下の場合は除外されることを検証 (Issue #1175)"""
    # 売出価格 3,000万円 に対して 理論予測価格 2,500万円（理論価格割れ・割高）
    rec = MockEvaluation(
        "investmentapartment",
        total_investment_score=85.0,
        first_stage_predicted_price=2500.0,
        id=201
    )
    prop = MockProperty(rec.property_url, 30000000)
    is_rec, reason, priority = _evaluate_candidate(rec, prop)
    assert is_rec is False
    assert reason == ""
    assert priority == 0.0

    # 売出価格 3,000万円 に対して 理論予測価格 4,000万円（理論価格が売出を上回り割安率25%）
    rec_pass = MockEvaluation(
        "investmentapartment",
        total_investment_score=85.0,
        first_stage_predicted_price=4000.0,
        id=202
    )
    is_rec2, reason2, priority2 = _evaluate_candidate(rec_pass, prop)
    assert is_rec2 is True
    assert "25.0% 割安" in reason2
    assert priority2 >= 70.0

def test_evaluate_investment_candidate_extreme_prediction_gap_passed():
    """二次スクリーニングが存在するため一次スクリーニングでの上限閾値は不要、予測価格が売出価格を下回る場合のみ除外されることを検証 (Issue #1348)"""
    # 例: フローラ・国分寺ＡＢ (売出価格 3,560万円 に対し 理論予測価格 174,133万円 -> 高い割安度でも一次スクリーニングは通過)
    rec_flora = MockEvaluation(
        "investmentapartment",
        total_investment_score=100.0,
        first_stage_predicted_price=174133.0,
        id=999
    )
    prop_flora = MockProperty(rec_flora.property_url, 35600000)
    is_rec, reason, _priority = _evaluate_candidate(rec_flora, prop_flora)
    assert is_rec is True
    assert "割安" in reason

    # 予測値が売出価格を下回る場合（売出価格 3,000万円 に対し 予測価格 500万円 -> 約0.16倍、割安でない）は除外
    rec_low = MockEvaluation(
        "investmentapartment",
        total_investment_score=85.0,
        first_stage_predicted_price=500.0,
        id=1000
    )
    prop_low = MockProperty(rec_low.property_url, 30000000)
    is_rec, reason, _priority = _evaluate_candidate(rec_low, prop_low)
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
