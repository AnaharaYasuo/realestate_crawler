# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.sumai1Parser import Sumai1MansionParser, Sumai1KodateParser, Sumai1TochiParser
from package.models.sumai1 import Sumai1Mansion, Sumai1Kodate, Sumai1Tochi

def test_sumai1_mansion_parser():
    parser = Sumai1MansionParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Mansion)
    
    html = """
    <html>
      <h1>テスト住まい1マンション</h1>
      <span class="price-value">4,980万円</span>
      <table>
        <tr><th>所在地</th><td>東京都新宿区西新宿1-1</td></tr>
        <tr><th>交通</th><td>JR山手線「新宿」駅 徒歩5分</td></tr>
        <tr><th>専有面積</th><td>65.20㎡</td></tr>
        <tr><th>間取り</th><td>2LDK</td></tr>
        <tr><th>築年月</th><td>2010年3月</td></tr>
        <tr><th>構造</th><td>SRC</td></tr>
        <tr><th>階数</th><td>8階</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テスト住まい1マンション"
    assert result.price == 49800000
    assert result.address == "東京都新宿区西新宿1-1"
    assert result.address1 == "東京都"
    assert result.address2 == "新宿区"
    assert result.address3 == "西新宿1-1"
    assert result.madori == "2LDK"
    assert float(result.senyuMenseki) == 65.2
    assert result.chikunengetsuStr == "2010年3月"
    assert result.kouzou == "SRC"
    assert result.floorType_kai == 8
    assert result.railway1 == "JR山手線"
    assert result.station1 == "新宿"
    assert result.railwayWalkMinute1 == 5

def test_sumai1_kodate_parser():
    parser = Sumai1KodateParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Kodate)
    
    html = """
    <html>
      <h1>テスト住まい1戸建</h1>
      <span class="price-value">7,500万円</span>
      <table>
        <tr><th>所在地</th><td>神奈川県川崎市中原区小杉町1-1</td></tr>
        <tr><th>交通</th><td>東急東横線「武蔵小杉」駅 徒歩4分</td></tr>
        <tr><th>土地面積</th><td>110.50㎡</td></tr>
        <tr><th>建物面積</th><td>105.00㎡</td></tr>
        <tr><th>築年月</th><td>2020年8月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テスト住まい1戸建"
    assert result.price == 75000000
    assert result.address == "神奈川県川崎市中原区小杉町1-1"
    assert result.address1 == "神奈川県"
    assert result.address2 == "川崎市中原区"
    assert result.address3 == "小杉町1-1"
    assert float(result.tochiMenseki) == 110.5
    assert float(result.tatemonoMenseki) == 105
    assert result.chikunengetsuStr == "2020年8月"
