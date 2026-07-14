# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.mizuhoParser import MizuhoMansionParser, MizuhoKodateParser, MizuhoTochiParser
from package.models.mizuho import MizuhoMansion, MizuhoKodate, MizuhoTochi

def test_mizuho_mansion_parser():
    parser = MizuhoMansionParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoMansion)
    
    html = """
    <html>
      <div class="detailTitle">
        <h4 class="h3Title">東京ミッドベイ勝どき<img class="newImg" src="icon.gif"></h4>
      </div>
      <table class="tableBasic gaiyouTable01 full">
        <tr><th>所在地</th><td>東京都中央区勝どき５丁目<button class="mapBtn">周辺地図</button></td></tr>
        <tr><th>交通</th><td>都営大江戸線 『勝どき』駅 徒歩8分</td></tr>
        <tr><th>価格</th><td>1億1,980万円</td></tr>
        <tr><th>専有面積</th><td>60.40㎡（約18.27坪）：壁芯</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>築年月</th><td>2012年02月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "東京ミッドベイ勝どき"
    assert result.price == 119800000
    assert result.address == "東京都中央区勝どき５丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "中央区"
    assert result.address3 == "勝どき５丁目"
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 60.4
    assert result.chikunengetsuStr == "2012年02月"
    assert result.railway1 == "都営大江戸線"
    assert result.station1 == "勝どき"
    assert result.railwayWalkMinute1 == 8

def test_mizuho_kodate_parser():
    parser = MizuhoKodateParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoKodate)
    
    html = """
    <html>
      <div class="detailTitle">
        <h4 class="h3Title">世田谷区中町の家</h4>
      </div>
      <table class="tableBasic gaiyouTable01 full">
        <tr><th>所在地</th><td>東京都世田谷区中町３丁目</td></tr>
        <tr><th>交通</th><td>東急大井町線 『等々力』駅 徒歩10分</td></tr>
        <tr><th>価格</th><td>1億2,800万円</td></tr>
        <tr><th>土地面積</th><td>115.50m²（約34.93坪）</td></tr>
        <tr><th>建物面積</th><td>98.50m²（約29.79坪）</td></tr>
        <tr><th>築年月</th><td>2018年10月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "世田谷区中町の家"
    assert result.price == 128000000
    assert result.address == "東京都世田谷区中町３丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "世田谷区"
    assert result.address3 == "中町３丁目"
    assert float(result.tochiMenseki) == 115.5
    assert float(result.tatemonoMenseki) == 98.5
    assert result.chikunengetsuStr == "2018年10月"
