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
    results = search_danchou_knowledge("指定容積率 容積余力 増床 建て替え", ptype_jp="一棟アパート", top_k=2)
    assert len(results) == 2
    assert any("容積" in r.get("category", "") or "容積" in r.get("title", "") for r in results)

    # マンション種別適合
    results_mansion = search_danchou_knowledge("修繕積立金 管理費 マンション", ptype_jp="中古マンション", top_k=2)
    assert any("マンション" in r.get("title", "") or "区分" in r.get("category", "") for r in results_mansion)

    # 土地種別適合
    results_land = search_danchou_knowledge("更地 水道管 擁壁", ptype_jp="土地", top_k=2)
    assert any("更地" in r.get("title", "") or "土地" in r.get("category", "") for r in results_land)

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

def test_property_type_specific_reports():
    """物件種別ごとに完全に差別化された定性評価が出力されることを検証 (Issue #1179)"""
    prop = MockProp()
    
    # 1. マンション
    eval_mansion = MockEval()
    rep_mansion = generate_professional_and_danchou_report(
        eval_rec=eval_mansion, prop=prop, ptype_jp="中古マンション",
        asking_price_man=4000, pred_price=5500.0, address="東京都品川区東大井", access="大井町駅 徒歩7分"
    )
    assert "区分" in rep_mansion["ai_evaluation_summary"] or "リノベ" in rep_mansion["highest_and_best_use"]
    assert "修繕積立金" in rep_mansion["ai_negative_points"]
    assert "更地化による出口戦略" not in rep_mansion["highest_and_best_use"]

    # 2. 土地
    eval_land = MockEval()
    rep_land = generate_professional_and_danchou_report(
        eval_rec=eval_land, prop=prop, ptype_jp="土地",
        asking_price_man=1500, pred_price=2200.0, address="埼玉県所沢市荒幡", access="下山口駅 徒歩10分"
    )
    assert "路線価" in rep_land["ai_evaluation_summary"] or "公示地価" in rep_land["ai_evaluation_summary"]
    assert "水道" in rep_land["ai_negative_points"] or "擁壁" in rep_land["ai_negative_points"]
    assert "プロパン" not in rep_land["ai_negative_points"]

    # 3. 戸建
    eval_kodate = MockEval()
    rep_kodate = generate_professional_and_danchou_report(
        eval_rec=eval_kodate, prop=prop, ptype_jp="中古戸建",
        asking_price_man=800, pred_price=1200.0, address="埼玉県入間市仏子", access="仏子駅 徒歩15分"
    )
    assert "戸建" in rep_kodate["ai_evaluation_summary"] or "戸建" in rep_kodate["highest_and_best_use"]
    assert "白蟻" in rep_kodate["ai_negative_points"] or "雨漏り" in rep_kodate["ai_negative_points"]

    # 各種別の団長コメントや最有効使用が互いに重複していないこと
    assert rep_mansion["highest_and_best_use"] != rep_land["highest_and_best_use"]
    assert rep_mansion["danchou_comment"] != rep_land["danchou_comment"]
    assert rep_land["danchou_comment"] != rep_kodate["danchou_comment"]
