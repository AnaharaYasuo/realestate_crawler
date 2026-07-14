# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.homesParser import HomesMansionParser, HomesKodateParser, HomesInvestmentApartmentParser
from package.models.homes import HomesMansion, HomesKodate, HomesInvestmentApartment

def test_homes_mansion_parser():
    parser = HomesMansionParser()
    item = parser.createEntity()
    assert isinstance(item, HomesMansion)
    
    html = """
    <html>
      <table>
        <tr>
          <td class="prg-nameTableItem">テストホームズマンション</td>
          <td class="prg-addressTableItem">東京都豊島区池袋1-1-1</td>
          <td class="prg-priceTableItem">4,280万円</td>
          <td class="prg-accessTableItem">東京メトロ丸ノ内線「池袋」駅 徒歩3分</td>
          <td class="prg-structureTableItem">SRC</td>
          <td class="prg-periodTableItem">2012年8月</td>
          <td class="prg-madoriTableItem">2LDK</td>
          <td class="prg-senyuAreaTableItem">60.20m²</td>
          <td class="prg-allNumberTableItem">80戸</td>
        </tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テストホームズマンション"
    assert result.address == "東京都豊島区池袋1-1-1"
    assert result.price == 42800000
    assert result.madori == "2LDK"
    assert float(result.senyuMenseki) == 60.2
    assert result.kouzou == "SRC"
    assert result.chikunengetsuStr == "2012年8月"

def test_homes_investment_parser():
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    assert isinstance(item, HomesInvestmentApartment)
    
    html = """
    <html>
      <table>
        <tr>
          <td class="prg-nameTableItem">テストホームズ投資アパート</td>
          <td class="prg-addressTableItem">東京都豊島区池袋2-2-2</td>
          <td class="prg-priceTableItem">1億2,000万円</td>
          <td class="prg-accessTableItem">東京メトロ丸ノ内線「池袋」駅 徒歩8分</td>
          <td class="prg-structureTableItem">鉄骨造</td>
          <td class="prg-periodTableItem">1998年11月</td>
          <td class="prg-landAreaTableItem">180.50m²</td>
          <td class="prg-houseAreaTableItem">220.00m²</td>
          <td class="prg-annualIncomeTableItem">960万円</td>
          <td class="prg-statusTableItem">賃貸中</td>
        </tr>
      </table>
      <span class="prg-rimawariTableItem">8.0％</span>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "テストホームズ投資アパート"
    assert result.address == "東京都豊島区池袋2-2-2"
    assert result.price == 120000000
    assert float(result.grossYield) == 8.0
    assert result.annualRent == 9600000
    assert float(result.tochiMenseki) == 180.50
    assert float(result.tatemonoMenseki) == 220.00
    assert result.kouzou == "鉄骨造"
    assert result.currentStatus == "賃貸中"
