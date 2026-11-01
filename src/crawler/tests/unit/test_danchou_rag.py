# -*- coding: utf-8 -*-
from package.ml.danchou_rag import (
    load_danchou_knowledge_base,
    search_danchou_knowledge,
    calculate_far_slack,
    SEED_KNOWLEDGE_BASE
)
from package.ml.report_generator import generate_professional_and_danchou_report

class MockProp:
    def __init__(self, tochi=100.0, tate=80.0, youseki="200%", traffic="JR山手線 渋谷駅 徒歩5分"):
        self.tochiMenseki = tochi
        self.tatemonoMenseki = tate
        self.yousekiStr = youseki
        self.traffic = traffic
        self.chikunengetsuStr = "1995年4月"
        self.kouzou = "木造"
        self.setsudou = "公道 西側 5.0m"

class MockEval:
    def __init__(self, estimated_sekisan_price=3500.0, cash_flow=150.0, dscr=1.45):
        self.estimated_sekisan_price = estimated_sekisan_price
        self.cash_flow = cash_flow
        self.dscr = dscr
        self.property_url = "https://example.com/test-prop"
        self.investment_rating = ""
        self.ai_evaluation_summary = ""
        self.highest_and_best_use = ""
        self.danchou_comment = ""
        self.ai_positive_points = ""
        self.ai_negative_points = ""
        self.far_slack_ratio = None

    def save(self):
        pass

def test_load_danchou_knowledge_base():
    """団長ナレッジベースがロード可能であることを検証"""
    kb = load_danchou_knowledge_base()
    assert isinstance(kb, list)
    assert len(kb) >= len(SEED_KNOWLEDGE_BASE)

def test_search_danchou_knowledge():
    """物件特徴に応じた団長エピソードの検索抽出検証"""
    # 容積余力キーワード
    results = search_danchou_knowledge("指定容積率 容積余力 増床 建て替え", top_k=2)
    assert len(results) == 2
    assert any("容積" in r.get("category", "") or "容積" in r.get("title", "") for r in results)

    # 指値・瞬間蒸発キーワード
    results2 = search_danchou_knowledge("指値 瞬間蒸発 現金買い付け 公道", top_k=2)
    assert len(results2) == 2
    assert any("指値" in r.get("title", "") or "買い付け" in r.get("category", "") for r in results2)

def test_calculate_far_slack():
    """未消化容積率の計算ロジック検証"""
    # 土地100㎡, 建物80㎡, 指定容積200% -> 現況80%, 未消化容積余力120%
    prop = MockProp(tochi=100.0, tate=80.0, youseki="200%")
    slack = calculate_far_slack(prop)
    assert slack == 120.0

    # 土地0の場合の安全弁
    prop_zero = MockProp(tochi=0.0, tate=80.0, youseki="200%")
    assert calculate_far_slack(prop_zero) is None

def test_generate_professional_and_danchou_report():
    """レポート生成エンジン（プロ鑑定＋団長目利き）の動作とeval_recへの反映検証"""
    prop = MockProp()
    eval_rec = MockEval()
    
    report = generate_professional_and_danchou_report(
        eval_rec=eval_rec,
        prop=prop,
        ptype_jp="一棟アパート",
        asking_price_man=3000,
        pred_price=4200.0,
        address="東京都渋谷区宇田川町",
        access="JR山手線 渋谷駅 徒歩5分"
    )
    
    assert "investment_rating" in report
    assert "ai_evaluation_summary" in report
    assert "highest_and_best_use" in report
    assert "danchou_comment" in report
    assert "ai_positive_points" in report
    assert "ai_negative_points" in report
    
    # 団長らしい辛口キーワードが含まれていること
    comment = report["danchou_comment"]
    assert any(w in comment for w in ["元付", "レントロール", "指値", "買い付け", "利回り", "積算", "獲物"])
    
    # eval_recに永続化反映されていること
    assert eval_rec.investment_rating != ""
    assert eval_rec.danchou_comment != ""
    assert eval_rec.far_slack_ratio == 120.0
