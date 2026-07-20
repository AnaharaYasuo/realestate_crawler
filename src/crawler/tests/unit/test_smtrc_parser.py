# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.smtrcParser import SmtrcMansionParser, SmtrcKodateParser
from package.models.smtrc import SmtrcMansion, SmtrcKodate

def test_smtrc_mansion_parser():
    parser = SmtrcMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcMansion)
    
    html = """
    <html>
      <h1>テストトラストマンション</h1>
      <span class="price-value">4,500万円</span>
      <table>
        <tr><th>所在地</th><td>東京都千代田区麹町1-1</td></tr>
        <tr><th>交通</th><td>東京メトロ有楽町線「麹町」駅 徒歩3分</td></tr>
        <tr><th>専有面積</th><td>70.50㎡</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>築年月</th><td>2015年5月</td></tr>
        <tr><th>構造</th><td>RC</td></tr>
        <tr><th>階数</th><td>5階</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テストトラストマンション"
    assert result.price == 45000000
    assert result.address == "東京都千代田区麹町1-1"
    assert result.address1 == "東京都"
    assert result.address2 == "千代田区"
    assert result.address3 == "麹町1-1"
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 70.5
    assert result.chikunengetsuStr == "2015年5月"
    assert result.kouzou == "RC"
    assert result.floorType_kai == 5
    assert result.railway1 == "東京メトロ有楽町線"
    assert result.station1 == "麹町"
    assert result.railwayWalkMinute1 == 3

def test_smtrc_kodate_parser():
    parser = SmtrcKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcKodate)
    
    html = """
    <html>
      <h1>テストトラスト戸建</h1>
      <span class="price-value">6,280万円</span>
      <table>
        <tr><th>所在地</th><td>神奈川県横浜市中区元町1-1</td></tr>
        <tr><th>交通</th><td>みなとみらい線「元町・中華街」駅 徒歩5分</td></tr>
        <tr><th>土地面積</th><td>100.20㎡</td></tr>
        <tr><th>建物面積</th><td>95.50㎡</td></tr>
        <tr><th>築年月</th><td>2018年10月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テストトラスト戸建"
    assert result.price == 62800000
    assert result.address == "神奈川県横浜市中区元町1-1"
    assert result.address1 == "神奈川県"
    assert result.address2 == "横浜市中区"
    assert result.address3 == "元町1-1"
    assert float(result.tochiMenseki) == 100.2
    assert float(result.tatemonoMenseki) == 95.5
    assert result.chikunengetsuStr == "2018年10月"
