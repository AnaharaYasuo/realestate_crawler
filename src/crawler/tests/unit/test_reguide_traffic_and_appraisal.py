import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from package.parser.reguideParser import ReguideInvestmentParser
from package.models.reguide import ReguideInvestment
from package.ml.appraisal_context import build_appraisal_context


def test_reguide_parser_populates_traffic():
    """RE-Guide パーサーが traffic から station1, railway1, walkMinutes1 を正しく設定することを検証"""
    html = """
    <html>
    <head><title>テストアパート</title></head>
    <body>
        <h1>テスト物件</h1>
        <table>
            <tr><th>物件名</th><td>★オーナーチェンジ★テストアパート</td></tr>
            <tr><th>価格</th><td>5,000万円</td></tr>
            <tr><th>所在地</th><td>東京都あきる野市牛沼</td></tr>
            <tr><th>交通</th><td>五日市線 「秋川」駅 徒歩30分</td></tr>
            <tr><th>満室想定表面利回り</th><td>6.3%</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = ReguideInvestmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.re-guide.jp/investment/421509/"
    
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    
    assert parsed_item.traffic == "五日市線 「秋川」駅 徒歩30分"
    assert parsed_item.station1 == "秋川"
    assert parsed_item.railway1 == "五日市線"
    assert parsed_item.railwayWalkMinute1 == 30


def test_appraisal_context_fallback_traffic():
    """station1 が空でも prop.traffic から駅名を抽出して乗降客数を取得することを検証"""
    prop = MagicMock()
    prop.station1 = ""
    prop.station = ""
    prop.traffic = "五日市線 「秋川」駅 徒歩30分"
    prop.prefecture = "東京都"
    prop.city = "あきる野市"
    prop.address = "東京都あきる野市牛沼"
    prop.propertyName = "テストアパート"
    prop.floor_area_ratio = 200.0

    with patch("package.ml.appraisal_context.extract_clean_address", return_value=("東京都", "あきる野市", "", "reguide")), \
         patch("package.ml.appraisal_context.query_station_volume", return_value=10700) as mock_st:
        ctx = build_appraisal_context(prop, "一棟アパート")
        assert ctx["station"] == "秋川"
        assert ctx["passenger_volume"] == 10700
        mock_st.assert_called_with("秋川")
