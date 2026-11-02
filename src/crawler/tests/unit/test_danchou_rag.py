from unittest.mock import patch
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
    
    mock_ai = {
        "investment_rating": "A",
        "ai_evaluation_summary": "渋谷徒歩5分で積算価格を大きく下回る歪み価格設定。公道接道で資産性高。",
        "highest_and_best_use": "現況満室賃貸維持後、将来的な更地化・高密度化によるデベロッパー向け売却",
        "danchou_comment": "公道接道で積算割れなし。これは瞬間蒸発する獲物。挨拶代わりの指値など入れずに即買い付けを叩き込むべき。",
        "ai_positive_points": "公道幅員5m、容積余力120%、駅近徒歩5分",
        "ai_negative_points": "築古木造のため定期的な外壁修繕コストを要する"
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch("package.ml.report_generator._call_gemini_api", return_value=mock_ai):
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
    mock_mansion = {
        "investment_rating": "B",
        "ai_evaluation_summary": "品川区東大井の区分レジデンス。利回りは標準的だが実需賃貸需要が底堅い。",
        "highest_and_best_use": "水回り設備のリノベを実施した上での単身実需向け再販または高利回り賃貸",
        "danchou_comment": "区分マンションは管理費と修繕積立金の滞納および直近の値上げ予定をまず洗え。",
        "ai_positive_points": "駅近徒歩7分、利便性良好",
        "ai_negative_points": "修繕積立金の値上げリスク、専有部配管の劣化懸念"
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch("package.ml.report_generator._call_gemini_api", return_value=mock_mansion):
        rep_mansion = generate_professional_and_danchou_report(
            eval_rec=eval_mansion, prop=prop, ptype_jp="中古マンション",
            asking_price_man=4000, pred_price=5500.0, address="東京都品川区東大井", access="大井町駅 徒歩7分"
        )
    assert "区分" in rep_mansion["ai_evaluation_summary"] or "リノベ" in rep_mansion["highest_and_best_use"]
    assert "修繕積立金" in rep_mansion["ai_negative_points"]
    assert "更地化による出口戦略" not in rep_mansion["highest_and_best_use"]

    # 2. 土地
    eval_land = MockEval()
    mock_land = {
        "investment_rating": "A",
        "ai_evaluation_summary": "所沢市荒幡の整形地。路線価対比で大幅な割安感あり。",
        "highest_and_best_use": "更地渡しによる戸建ビルダー向け分譲用地ハメ込み",
        "danchou_comment": "土地は公道接道とインフラ引き込みが全て。擁壁や越境があれば鬼指値の好機。",
        "ai_positive_points": "整形地、接道幅員十分",
        "ai_negative_points": "擁壁の安全性確認、水道管の引き直し費用リスク"
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch("package.ml.report_generator._call_gemini_api", return_value=mock_land):
        rep_land = generate_professional_and_danchou_report(
            eval_rec=eval_land, prop=prop, ptype_jp="土地",
            asking_price_man=1500, pred_price=2200.0, address="埼玉県所沢市荒幡", access="下山口駅 徒歩10分"
        )
    assert "路線価" in rep_land["ai_evaluation_summary"] or "公示地価" in rep_land["ai_evaluation_summary"]
    assert "水道" in rep_land["ai_negative_points"] or "擁壁" in rep_land["ai_negative_points"]
    assert "プロパン" not in rep_land["ai_negative_points"]

    # 3. 戸建
    eval_kodate = MockEval()
    mock_kodate = {
        "investment_rating": "B+",
        "ai_evaluation_summary": "入間市仏子の再生向け戸建住宅。実質利回り15%超の賃貸運用が見込める。",
        "highest_and_best_use": "DIY低コスト再生による長期ファミリー賃貸運用",
        "danchou_comment": "ボロ戸建は雨漏りと白蟻と傾きを床下から確認せよ。指値は挨拶代わりにぶち込め。",
        "ai_positive_points": "土地値近傍の割安売出価格、実質利回り期待値大",
        "ai_negative_points": "雨漏り・白蟻被害の修繕リスク、汲み取り設備の更新費用"
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch("package.ml.report_generator._call_gemini_api", return_value=mock_kodate):
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


def test_multi_perspective_appraisal_and_mansion_review():
    """地域・駅・ハザード・物件・マンションレビュー過去取引事例を踏まえた多面プロ鑑定の検証 (Issue #1197)"""
    from package.ml.appraisal_context import build_appraisal_context, format_appraisal_context_text
    from package.ml.report_generator import generate_professional_and_danchou_report
    from unittest.mock import MagicMock, patch

    eval_rec = MagicMock()
    eval_rec.property_url = "https://example.com/condo"
    eval_rec.estimated_sekisan_price = 60000000

    prop = MagicMock()
    prop.address1 = ""
    prop.address2 = ""
    prop.address = "東京都品川区小山3丁目"
    prop.propertyName = "パークシティ武蔵小山ザタワー"
    prop.station1 = "武蔵小山"
    prop.senyuMenseki = 65.0
    prop.floor_area_ratio = 400.0

    mock_mr_data = {
        "mansion_name": "パークシティ武蔵小山ザタワー",
        "estimated_tsubo_price_man": 1023,
        "estimated_market_price_man": 18861,
        "history_samples": ["31階 / 2LDK / 65m2 / 18500万円"]
    }

    with patch("package.ml.appraisal_context.fetch_mansion_review_data", return_value=mock_mr_data):
        ctx = build_appraisal_context(prop, ptype_jp="中古マンション")
        assert ctx["prefecture"] == "東京都"
        assert ctx["city"] == "品川区"
        assert ctx["mansion_review"] is not None
        assert ctx["mansion_review"]["estimated_tsubo_price_man"] == 1023

        formatted = format_appraisal_context_text(ctx)
        assert "自治体マクロ指標" in formatted
        assert "国交省ハザードリスク指標" in formatted
        assert "マンションレビュー過去取引事例データ" in formatted
        assert "1023万円/坪" in formatted

    mock_llm_response = {
        "investment_rating": "AAA",
        "area_evaluation": "品川区小山は城南エリア屈指の居住人気と安定した人口増を維持。",
        "station_evaluation": "東急目黒線急行停車の武蔵小山駅徒歩1分で都心直通の圧倒的利便性。",
        "hazard_evaluation": "武蔵野台地に立地し浸水想定区域・土砂災害警戒区域のいずれも対象外。",
        "property_evaluation": "大手デベ分譲タワーレジデンス、売出価格は積算対比で明確に割安。",
        "mansion_market_evaluation": "マンションレビュー推定相場坪単価1,023万に対し、本物件の売出坪単価850万は明白な市場歪み。",
        "highest_and_best_use": "富裕層ファミリー向け実需居住または高利回り賃貸、出口リセール極めて良好。",
        "danchou_comment": "武蔵小山駅前タワーでこの歪みは秒で攫われる。指値ゴネせず満額即決で叩き込め！",
        "ai_positive_points": "立地・駅力、相場坪単価対比の割安度、安定地盤",
        "ai_negative_points": "管理費・修繕積立金の滞納率確認、専有部配管劣化の確認"
    }

    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), \
         patch("package.ml.report_generator._call_gemini_api", return_value=mock_llm_response), \
         patch("package.ml.appraisal_context.fetch_mansion_review_data", return_value=mock_mr_data):
        report = generate_professional_and_danchou_report(
            eval_rec=eval_rec,
            prop=prop,
            ptype_jp="中古マンション",
            asking_price_man=7500,
            pred_price=9200.0,
            address="東京都品川区小山3丁目",
            access="武蔵小山駅 徒歩1分"
        )

    assert report["investment_rating"] == "AAA"
    assert eval_rec.area_evaluation == mock_llm_response["area_evaluation"]
    assert eval_rec.station_evaluation == mock_llm_response["station_evaluation"]
    assert eval_rec.hazard_evaluation == mock_llm_response["hazard_evaluation"]
    assert eval_rec.property_spec_evaluation == mock_llm_response["property_evaluation"]
    assert eval_rec.mansion_market_evaluation == mock_llm_response["mansion_market_evaluation"]
    assert "地域要因" in eval_rec.ai_evaluation_summary
    assert "過去取引事例" in eval_rec.ai_evaluation_summary
    assert report["area_evaluation"] == mock_llm_response["area_evaluation"]
    assert report["hazard_evaluation"] == mock_llm_response["hazard_evaluation"]
    assert report["mansion_market_evaluation"] == mock_llm_response["mansion_market_evaluation"]
