# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.athomeParser import AthomeMansionParser, AthomeKodateParser, AthomeInvestmentApartmentParser
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment

def test_athome_mansion_parser():
    parser = AthomeMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeMansion)
    
    html = """
    <html>
      <div id="detailTitleArea"><h2><em>テストアットホームマンション</em></h2></div>
      <table summary="物件詳細">
        <tr><th>所在地</th><td>東京都新宿区西新宿1-1-1</td></tr>
        <tr><th>価格</th><td>5,500万円</td></tr>
        <tr><th>交通</th><td>JR山手線「新宿」駅 徒歩5分</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>専有面積</th><td>75.50m²</td></tr>
        <tr><th>階建 / 階</th><td>10階建 / 5階</td></tr>
        <tr><th>主要採光面</th><td>南</td></tr>
        <tr><th>総戸数</th><td>50戸</td></tr>
        <tr><th>管理費等</th><td>15,000円</td></tr>
        <tr><th>修繕積立金</th><td>10,000円</td></tr>
        <tr><th>建物構造</th><td>RC</td></tr>
        <tr><th>築年月</th><td>2018年3月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テストアットホームマンション"
    assert result.address == "東京都新宿区西新宿1-1-1"
    assert result.price == 55000000
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 75.5
    assert result.kouzou == "RC"
    assert result.chikunengetsuStr == "2018年3月"

def test_athome_investment_parser():
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeInvestmentApartment)
    
    html = """
    <html>
      <div id="detailTitleArea"><h2><em>テスト投資アパート</em></h2></div>
      <table summary="物件詳細">
        <tr><th>所在地</th><td>東京都新宿区西新宿2-2-2</td></tr>
        <tr><th>価格</th><td>9,800万円</td></tr>
        <tr><th>交通</th><td>JR山手線「新宿」駅 徒歩10分</td></tr>
        <tr><th>利回り</th><td>6.5%</td></tr>
        <tr><th>想定賃料</th><td>637万円</td></tr>
        <tr><th>建物面積</th><td>150.20m²</td></tr>
        <tr><th>土地面積</th><td>200.00m²</td></tr>
        <tr><th>建物構造</th><td>木造</td></tr>
        <tr><th>築年月</th><td>2015年5月</td></tr>
        <tr><th>現況</th><td>満室賃貸中</td></tr>
        <tr><th>総戸数</th><td>10戸</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テスト投資アパート"
    assert result.address == "東京都新宿区西新宿2-2-2"
    assert result.price == 98000000
    assert float(result.grossYield) == 6.5
    assert result.annualRent == 6370000
    assert float(result.tatemonoMenseki) == 150.20
    assert float(result.tochiMenseki) == 200.00
    assert result.kouzou == "木造"
    assert result.currentStatus == "満室賃貸中"
