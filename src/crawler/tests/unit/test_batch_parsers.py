# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.odakyuParser import OdakyuMansionParser, OdakyuKodateParser, OdakyuInvestmentParser
from package.parser.totateParser import TotateMansionParser, TotateKodateParser
from package.parser.daiwaParser import DaiwaMansionParser, DaiwaKodateParser
from package.parser.smtrcParser import SmtrcInvestmentParser
from package.parser.sumai1Parser import Sumai1InvestmentParser
from package.parser.mizuhoParser import MizuhoInvestmentParser
from package.models.odakyu import OdakyuMansion, OdakyuKodate, OdakyuInvestment
from package.models.totate import TotateMansion, TotateKodate
from package.models.daiwa import DaiwaMansion, DaiwaKodate
from package.models.smtrc import SmtrcInvestment
from package.models.sumai1 import Sumai1Investment
from package.models.mizuho import MizuhoInvestment

def test_odakyu_mansion_parser():
    parser = OdakyuMansionParser()
    item = parser.createEntity()
    assert isinstance(item, OdakyuMansion)
    
    html = """
    <html>
      <h1>リーフィアレジデンス成城</h1>
      <table class="tableBasic">
        <tr><th>所在地</th><td>東京都世田谷区成城６丁目</td></tr>
        <tr><th>交通</th><td>小田急線 『成城学園前』駅 徒歩3分</td></tr>
        <tr><th>価格</th><td>1億4,800万円</td></tr>
        <tr><th>専有面積</th><td>75.20㎡</td></tr>
        <tr><th>間取り</th><td>2LDK</td></tr>
        <tr><th>築年月</th><td>2015年10月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "リーフィアレジデンス成城"
    assert result.price == 148000000
    assert result.address == "東京都世田谷区成城６丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "世田谷区"
    assert result.address3 == "成城６丁目"
    assert result.madori == "2LDK"
    assert float(result.senyuMenseki) == 75.2
    assert result.chikunengetsuStr == "2015年10月"
    assert result.railway1 == "小田急線"
    assert result.station1 == "成城学園前"
    assert result.railwayWalkMinute1 == 3

def test_totate_mansion_parser():
    parser = TotateMansionParser()
    item = parser.createEntity()
    assert isinstance(item, TotateMansion)
    
    html = """
    <html>
      <h1>Brillia代々木公園</h1>
      <table>
        <tr><th>所在地</th><td>東京都渋谷区富ヶ谷１丁目</td></tr>
        <tr><th>交通</th><td>東京メトロ千代田線 『代々木公園』駅 徒歩4分</td></tr>
        <tr><th>価格</th><td>1億8,500万円</td></tr>
        <tr><th>専有面積</th><td>82.40㎡</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>築年月</th><td>2018年05月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "Brillia代々木公園"
    assert result.price == 185000000
    assert result.address == "東京都渋谷区富ヶ谷１丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "渋谷区"
    assert result.address3 == "富ヶ谷１丁目"
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 82.4
    assert result.chikunengetsuStr == "2018年05月"

def test_daiwa_mansion_parser():
    parser = DaiwaMansionParser()
    item = parser.createEntity()
    assert isinstance(item, DaiwaMansion)
    
    html = """
    <html>
      <h1>プレミストプレシア勝どき</h1>
      <table>
        <tr><th>所在地</th><td>東京都中央区勝どき４丁目</td></tr>
        <tr><th>交通</th><td>都営大江戸線 『勝どき』駅 徒歩5分</td></tr>
        <tr><th>価格</th><td>1億3,200万円</td></tr>
        <tr><th>専有面積</th><td>70.15㎡</td></tr>
        <tr><th>間取り</th><td>3LDK</td></tr>
        <tr><th>築年月／完成予定年月</th><td>2014年03月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "プレミストプレシア勝どき"
    assert result.price == 132000000
    assert result.address == "東京都中央区勝どき４丁目"
    assert result.address1 == "東京都"
    assert result.address2 == "中央区"
    assert result.address3 == "勝どき４丁目"
    assert result.madori == "3LDK"
    assert float(result.senyuMenseki) == 70.15
    assert result.chikunengetsuStr == "2014年03月"


def test_smtrc_investment_parser():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcInvestment)
    
    html = """
    <html>
      <h1>新宿区一棟アパート</h1>
      <table>
        <tr><th>所在地</th><td>東京都新宿区西新宿３丁目</td></tr>
        <tr><th>交通</th><td>都営大江戸線 「都庁前」駅 徒歩5分</td></tr>
        <tr><th>価格</th><td>1億5,000万円</td></tr>
        <tr><th>利回り</th><td>6.50%</td></tr>
        <tr><th>年間想定収入</th><td>975万円</td></tr>
        <tr><th>現況</th><td>満室</td></tr>
        <tr><th>構造</th><td>木造</td></tr>
        <tr><th>築年月</th><td>2018年04月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "新宿区一棟アパート"
    assert result.price == 150000000
    assert float(result.grossYield) == 6.5
    assert result.annualRent == 9750000
    assert result.currentStatus == "満室"
    assert result.propertyType == "Apartment"
    assert result.kouzou == "木造"
    assert result.chikunengetsuStr == "2018年04月"


def test_sumai1_investment_parser():
    parser = Sumai1InvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Investment)
    
    html = """
    <html>
      <h1>港区一棟ビル</h1>
      <table>
        <tr><th>所在地</th><td>東京都港区新橋２丁目</td></tr>
        <tr><th>交通</th><td>JR山手線 「新橋」駅 徒歩4分</td></tr>
        <tr><th>価格</th><td>8億2,000万円</td></tr>
        <tr><th>表面利回り</th><td>4.80%</td></tr>
        <tr><th>年間想定収入</th><td>3,936万円</td></tr>
        <tr><th>現況</th><td>一部賃貸中</td></tr>
        <tr><th>構造</th><td>鉄骨鉄筋コンクリート造</td></tr>
        <tr><th>築年月</th><td>1995年11月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "港区一棟ビル"
    assert result.price == 820000000
    assert float(result.grossYield) == 4.8
    assert result.annualRent == 39360000
    assert result.currentStatus == "一部賃貸中"
    assert result.propertyType == "Building"
    assert result.kouzou == "鉄骨鉄筋コンクリート造"
    assert result.chikunengetsuStr == "1995年11月"


def test_mizuho_investment_parser():
    parser = MizuhoInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoInvestment)
    
    html = """
    <html>
      <h1>豊島区一棟アパート</h1>
      <table>
        <tr><th>所在地</th><td>東京都豊島区池袋４丁目</td></tr>
        <tr><th>交通</th><td>JR山手線 「池袋」駅 徒歩8分</td></tr>
        <tr><th>価格</th><td>2億1,000万円</td></tr>
        <tr><th>利回り</th><td>5.90%</td></tr>
        <tr><th>年間想定収入</th><td>1,239万円</td></tr>
        <tr><th>現況</th><td>満室</td></tr>
        <tr><th>構造</th><td>軽量鉄骨造</td></tr>
        <tr><th>築年月</th><td>2020年03月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "豊島区一棟アパート"
    assert result.price == 210000000
    assert float(result.grossYield) == 5.9
    assert result.annualRent == 12390000
    assert result.currentStatus == "満室"
    assert result.propertyType == "Apartment"
    assert result.kouzou == "軽量鉄骨造"
    assert result.chikunengetsuStr == "2020年03月"


def test_odakyu_investment_parser():
    parser = OdakyuInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, OdakyuInvestment)
    
    html = """
    <html>
      <h1>世田谷区一棟マンション</h1>
      <table>
        <tr><th>所在地</th><td>東京都世田谷区桜丘３丁目</td></tr>
        <tr><th>交通</th><td>小田急線 「千歳船橋」駅 徒歩10分</td></tr>
        <tr><th>価格</th><td>3億4,000万円</td></tr>
        <tr><th>表面利回り</th><td>5.20%</td></tr>
        <tr><th>年間想定収入</th><td>1,768万円</td></tr>
        <tr><th>現況</th><td>満室</td></tr>
        <tr><th>構造</th><td>RC造</td></tr>
        <tr><th>築年月</th><td>2012年09月</td></tr>
      </table>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parser._parsePropertyDetailPage(item, soup)
    
    assert result.propertyName == "世田谷区一棟マンション"
    assert result.price == 340000000
    assert float(result.grossYield) == 5.2
    assert result.annualRent == 17680000
    assert result.currentStatus == "満室"
    assert result.propertyType == "Mansion"
    assert result.kouzou == "RC造"
    assert result.chikunengetsuStr == "2012年09月"


