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

def test_build_recommendation_msg_rich_content():
    """刷新された通知メッセージに所在地、駅、3面価格、割安額、プロ鑑定、団長目利きが含まれることの検証"""
    prop = MockPropMsg()
    eval_rec = MockEvalMsg()

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
    assert "プロフェッショナル物件評価レポート" in msg
    assert "最有効使用・容積余力ポテンシャル" in msg
    assert "元祖・狼旅団 団長の辛口実戦目利き" in msg
    assert "詳細URL: https://example.com/sunrise-hachioji" in msg
