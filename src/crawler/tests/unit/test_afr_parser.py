# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.afrParser import AfrMansionParser, AfrKodateParser, AfrTochiParser
from package.models.afr import AfrMansion, AfrKodate, AfrTochi

def test_afr_mansion_parser():
    parser = AfrMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AfrMansion)
    
    html = """
    <html>
      <h2>アトラス新宿余丁町</h2>
      <table class="table">
        <tr><th>所在地</th><td>東京都新宿区余丁町</td></tr>
        <tr><th>交通</th><td>都営大江戸線「若松河田」駅 徒歩4分</td></tr>
        <tr><th>価格</th><td>7,980万円</td></tr>
        <tr><th>専有面積</th><td>55.30㎡（16.72坪）</td></tr>
        <tr><th>間取り</th><td>2LDK</td></tr>
        <tr><th>築年月</th><td>2020年10月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "アトラス新宿余丁町"
    assert result.price == 79800000
    assert result.address == "東京都新宿区余丁町"
    assert result.address1 == "東京都"
    assert result.address2 == "新宿区"
    assert result.address3 == "余丁町"
    assert result.madori == "2LDK"
    assert float(result.senyuMenseki) == 55.3
    assert result.chikunengetsuStr == "2020年10月"
    assert result.railway1 == "都営大江戸線"
    assert result.station1 == "若松河田"
    assert result.railwayWalkMinute1 == 4

def test_afr_kodate_parser():
    parser = AfrKodateParser()
    item = parser.createEntity()
    assert isinstance(item, AfrKodate)
    
    html = """
    <html>
      <h2>松戸市二十世紀が丘美野里町の家</h2>
      <table class="table">
        <tr><th>所在地</th><td>千葉県松戸市二十世紀が丘美野里町</td></tr>
        <tr><th>交通</th><td>北総鉄道「北国分」駅 徒歩19分</td></tr>
        <tr><th>価格</th><td>6,480万円</td></tr>
        <tr><th>土地面積</th><td>196.49m²（59.43坪）</td></tr>
        <tr><th>建物面積</th><td>79.25m²（23.97坪）</td></tr>
        <tr><th>築年月</th><td>2019年07月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "松戸市二十世紀が丘美野里町の家"
    assert result.price == 64800000
    assert result.address == "千葉県松戸市二十世紀が丘美野里町"
    assert result.address1 == "千葉県"
    assert result.address2 == "松戸市"
    assert result.address3 == "二十世紀が丘美野里町"
    assert float(result.tochiMenseki) == 196.49
    assert float(result.tatemonoMenseki) == 79.25
    assert result.chikunengetsuStr == "2019年07月"
