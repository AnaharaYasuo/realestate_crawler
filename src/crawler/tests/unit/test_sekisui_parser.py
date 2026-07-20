# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.sekisuiParser import SekisuiMansionParser, SekisuiKodateParser
from package.models.sekisui import SekisuiMansion, SekisuiKodate

def test_sekisui_mansion_parser():
    parser = SekisuiMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiMansion)
    
    html = """
    <html>
      <h1 class="detail-header__title">グランドメゾン西新宿</h1>
      <span class="detail-header__price">6,800万円</span>
      <table>
        <tr><th>所在地</th><td>東京都新宿区西新宿3丁目</td></tr>
        <tr><th>交通</th><td>都営大江戸線「都庁前」駅 徒歩4分</td></tr>
        <tr><th>専有面積</th><td>72.50㎡</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>築年月</th><td>2015年11月</td></tr>
        <tr><th>構造</th><td>RC</td></tr>
        <tr><th>階数</th><td>12階</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "グランドメゾン西新宿"
    assert result.price == 68000000
    assert result.address == "東京都新宿区西新宿3丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "新宿区"
    assert result.address3 == "西新宿3丁目"
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 72.5
    assert result.chikunengetsuStr == "2015年11月"
    assert result.floorType_kai == 12
    assert result.railway1 == "都営大江戸線"
    assert result.station1 == "都庁前"
    assert result.railwayWalkMinute1 == 4

def test_sekisui_kodate_parser():
    parser = SekisuiKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiKodate)
    
    html = """
    <html>
      <h1 class="detail-header__title">シャーウッド小杉</h1>
      <span class="detail-header__price">8,980万円</span>
      <table>
        <tr><th>所在地</th><td>神奈川県川崎市中原区小杉町2丁目</td></tr>
        <tr><th>交通</th><td>東急東横線「武蔵小杉」駅 徒歩6分</td></tr>
        <tr><th>土地面積</th><td>125.00㎡</td></tr>
        <tr><th>建物面積</th><td>115.30㎡</td></tr>
        <tr><th>築年月</th><td>2018年5月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "シャーウッド小杉"
    assert result.price == 89800000
    assert result.address == "神奈川県川崎市中原区小杉町2丁目"
    assert result.address1 == "神奈川県"
    assert result.address2 == "川崎市中原区"
    assert result.address3 == "小杉町2丁目"
    assert float(result.tochiMenseki) == 125.0
    assert float(result.tatemonoMenseki) == 115.3
    assert result.chikunengetsuStr == "2018年5月"
