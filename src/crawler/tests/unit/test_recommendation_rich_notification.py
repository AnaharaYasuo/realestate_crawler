from unittest.mock import patch
# -*- coding: utf-8 -*-
from scripts.ops.send_recommendations import _build_recommendation_msg, _format_access_and_area

class MockPropMsg:
    def __init__(self):
        self.price = 28000000
        self.propertyName = "サンライズ八王子"
        self.address = "東京都八王子市子安町"
        self.address1 = ""
        self.address2 = ""
        self.address3 = ""
        self.addressKyoto = ""
        self.railway1 = "京王線"
        self.station1 = "京王八王子駅"
        self.railwayWalkMinute1Str = "6分"
        self.traffic = ""
        self.chikunengetsuStr = "1992年3月"
        self.chikunenki = ""
        self.madori = "1K×8戸"
        self.kenpeiStr = "60%"
        self.yousekiStr = "200%"
        self.tochiMensekiStr = "120㎡"
        self.tatemonoMensekiStr = "100㎡"
        self.senyuMensekiStr = ""
        self.tochiMenseki = 120.0
        self.tatemonoMenseki = 100.0
        self.kouzou = "木造"
        self.setsudou = "公道 南側 6.0m"
        self.inputDate = "2026-11-01"

class MockEvalMsg:
    def __init__(self):
        self.property_type = "investmentapartment"
        self.first_stage_predicted_price = 3800.0
        self.second_stage_predicted_price = None
        self.estimated_sekisan_price = 3200.0
        self.cash_flow = 160.0
        self.dscr = 1.48
        self.property_url = "https://example.com/sunrise-hachioji"
        self.investment_rating = ""
        self.ai_evaluation_summary = ""
        self.highest_and_best_use = ""
        self.danchou_comment = ""
        self.ai_positive_points = ""
        self.ai_negative_points = ""
        self.far_slack_ratio = None

    def save(self):
        pass

def test_format_access_and_area():
    """所在地・駅情報の整形テスト"""
    prop = MockPropMsg()
    access, area = _format_access_and_area(prop)
    assert "京王線 京王八王子駅 徒歩6分" in access
    assert "土地: 120㎡" in area
    assert "建物: 100㎡" in area


def test_format_access_with_bus():
    """バス利用情報が含まれる場合のアクセス表記整形テスト (Issue #1225)"""
    class MockBusProp:
        railway1 = "中央線"
        station1 = "三鷹"
        busUse1 = 1
        busWalkMinute1Str = "25"
        busWalkMinute1 = 25
        busStation1 = "中原三丁目"
        railwayWalkMinute1Str = "1"
        traffic = ""
        senyuMensekiStr = "72.79㎡"
        tochiMensekiStr = ""
        tatemonoMensekiStr = ""

    prop = MockBusProp()
    access, area = _format_access_and_area(prop)
    assert access == "中央線 三鷹 バス25分(停 中原三丁目) 徒歩1分"
    assert "専有: 72.79㎡" in area


def test_appraisal_context_cache_and_income_format():
    """AI鑑定コンテキストのキャッシュ初期化および平均所得フォーマットテスト (Issue #1225)"""
    from package.ml.appraisal_context import build_appraisal_context, format_appraisal_context_text
    from package.ml.features.reference_data import _muni_cache, MunicipalRecord, reset_reference_caches

    reset_reference_caches()
    # 単体テスト用インメモリキャッシュに世田谷区データを注入
    _muni_cache[("東京都", "世田谷区")] = MunicipalRecord(
        prefecture="東京都",
        city="世田谷区",
        population_growth_rate=0.4,
        average_income=5600,
        total_population=100000,
        income_growth_rate=0.0,
        population_density=4000.0,
    )

    class DummyProp:
        address1 = "東京都"
        address2 = "世田谷区南烏山"
        station1 = "芦花公園"
        company = "livable"

    prop = DummyProp()
    try:
        ctx = build_appraisal_context(prop, "戸建（投資用）")
        assert ctx["prefecture"] == "東京都"
        assert ctx["city"] == "世田谷区"

        formatted = format_appraisal_context_text(ctx)
        # キャッシュのaverage_income=5600（千円）から正確に560万円に換算されることを検証
        assert "平均所得 560万円" in formatted
        assert "平均所得 3000万円" not in formatted
        assert "平均所得 5600万円" not in formatted
    finally:
        reset_reference_caches()

def test_build_recommendation_msg_rich_content():
    """刷新された通知メッセージに所在地、駅、3面価格、割安額、プロ鑑定、団長目利きが含まれることの検証"""
    prop = MockPropMsg()
    eval_rec = MockEvalMsg()

    mock_ai = {
        "investment_rating": "A",
        "ai_evaluation_summary": "八王子駅徒歩6分、積算価格対比割安。",
        "highest_and_best_use": "最有効使用・容積余力ポテンシャルの最大化",
        "danchou_comment": "元祖・狼旅団 団長の辛口実戦目利き：即買い付け推奨。",
        "ai_positive_points": "好立地",
        "ai_negative_points": "築古"
    }
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch("package.ml.report_generator._call_gemini_api", return_value=mock_ai):
        msg = _build_recommendation_msg(
            eval_rec=eval_rec,
            prop=prop,
            reason="【市場予測価格より 26.3% 割安（投資お宝物件！）】",
            p_name=prop.propertyName
        )

    # 1. ヘッダー・割安度
    assert "サンライズ八王子 (一棟アパート)" in msg
    assert "売出価格: 2800万円" in msg
    assert "理論予測価格: 3800万円" in msg
    assert "割安度: -1000万円" in msg
    assert "想定積算価格: 3200.0万円" in msg

    # 2. 所在地・最寄り駅
    assert "所在地: 東京都八王子市子安町" in msg
    assert "最寄り駅: 京王線 京王八王子駅 徒歩6分" in msg

    # 3. プロ鑑定レポート ＆ 団長講評
    assert "プロフェッショナル多面鑑定評価レポート" in msg
    assert "最有効使用・容積余力ポテンシャル" in msg
    assert "元祖・狼旅団 団長の辛口実戦目利き" in msg
    assert "詳細URL: https://example.com/sunrise-hachioji" in msg
