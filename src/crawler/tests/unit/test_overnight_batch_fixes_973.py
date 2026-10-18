import pytest
from bs4 import BeautifulSoup
from decimal import Decimal
from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiInvestmentKodateParser
from package.parser.athomeParser import AthomeTochiParser
from package.parser.baseParser import ParserBase, SkipPropertyException
from package.utils.data_validator import PropertyDataValidator

def test_daikyo_column_url_is_rejected():
    """大京穴吹のコラム/記事URL (/sumai/detail/1030/) が非物件URLとしてスキップされること"""
    url = "https://www.daikyo-anabuki.co.jp/sumai/detail/1030/"
    with pytest.raises(SkipPropertyException):
        ParserBase._reject_non_property_url(url)

def test_mitsui_traffic_split_inline_string():
    """三井の1行結合交通文字列が複数路線に正しく分割抽出されること"""
    html = """
    <html>
      <body>
        <table>
          <tr><th>交通</th><td>東京メトロ日比谷線六本木駅徒歩9分東京メトロ日比谷線広尾駅徒歩13分東京メトロ南北線麻布十番駅徒歩11分</td></tr>
          <tr><th>所在地</th><td>東京都港区元麻布３丁目</td></tr>
          <tr><th>価格</th><td>1億1,800万円</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser()
    lines = parser._parseTrafficLines(soup)
    assert len(lines) >= 3
    assert "六本木駅" in lines[0] or "六本木" in lines[0]
    assert "広尾駅" in lines[1] or "広尾" in lines[1]
    assert "麻布十番駅" in lines[2] or "麻布十番" in lines[2]

def test_mitsui_invest_kodate_skips_mansion_url():
    """三井投資用戸建てに区分マンションURLが混入した場合はスキップされること"""
    parser = MitsuiInvestmentKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKXBFA03/"
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, soup)

def test_athome_tochi_menseki_fallback():
    """アットホーム土地パーサーで面積が敷地面積や本文等から正しく抽出されること"""
    html = """
    <html>
      <body>
        <table>
          <tr><th>敷地面積</th><td>120.50㎡</td></tr>
          <tr><th>所在地</th><td>神奈川県横浜市中区</td></tr>
          <tr><th>価格</th><td>3,500万円</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeTochiParser()
    item = parser.createEntity()
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.tochiMenseki == Decimal("120.50")
