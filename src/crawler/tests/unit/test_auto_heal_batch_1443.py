# -*- coding: utf-8 -*-
"""Regression tests for auto-heal batch (#1444, #1447, #1450, #1451, #1452, #1453, #1455, #1458, #1463, #1468, #1470, #1480, #1774)."""

from bs4 import BeautifulSoup
import pytest

from package.parser.afrParser import AfrMansionParser, AfrTochiParser
from package.parser.athomeParser import AthomeInvestmentApartmentParser, AthomeKodateParser
from package.parser.baseParser import SkipPropertyException
from package.parser.daikyoParser import DaikyoMansionParser
from package.parser.misawaParser import MisawaMansionParser
from package.parser.mitsuiParser import MitsuiInvestmentKodateParser, MitsuiMansionParser
from package.parser.rearieParser import RearieMansionParser
from package.parser.sekisuiParser import SekisuiMansionParser
from package.parser.sumai1Parser import Sumai1MansionParser
from package.parser.tohoParser import TohoMansionParser, TohoTochiParser


def test_toho_tochi_combined_kenpei_youseki_1774():
    html = """
    <html><body>
      <h1>国立市東3丁目 土地18号地</h1>
      <table>
        <tr><th>価格</th><td>6,390万円</td></tr>
        <tr><th>所在地</th><td>東京都国立市東3丁目</td></tr>
        <tr><th>土地面積</th><td>110.00m²</td></tr>
        <tr><th>建ぺい率/容積率</th><td>50％／100％</td></tr>
      </table>
    </body></html>
    """
    parser = TohoTochiParser()
    soup = BeautifulSoup(html, "lxml")
    item = parser.createEntity()
    item.pageUrl = "https://www.toho-house.co.jp/sch/detail.php?k_number=85132-18&div=001"
    result = parser._parsePropertyDetailPage(item, soup)
    assert result.kenpei == "50％"
    assert result.youseki == "100％"


def test_toho_mansion_shozaikaisu_1480():
    html = """
    <html><body>
      <h1>クリオ片瀬江ノ島</h1>
      <table>
        <tr><th>価格</th><td>3,980万円</td></tr>
        <tr><th>所在地</th><td>藤沢市片瀬海岸2丁目</td></tr>
        <tr><th>専有面積</th><td>34.24m²</td></tr>
        <tr><th>間取り</th><td>1DK</td></tr>
        <tr><th>所在階数</th><td>5階</td></tr>
      </table>
    </body></html>
    """
    parser = TohoMansionParser()
    soup = BeautifulSoup(html, "lxml")
    item = parser.createEntity()
    item.pageUrl = "https://th-yokohama.com/estate_list_fujisawa/estate_detail_61380_1443.html"
    result = parser._parsePropertyDetailPage(item, soup)
    assert result.kaisu == "5階"


def test_afr_tochi_skips_kodate_and_parses_kenpeiritsu_kanji_1444():
    kodate_html = """
    <html><body>
      <h2>北九州市小倉北区篠崎5丁目</h2>
      <table>
        <tr><th>物件種別</th><td>中古一戸建て</td></tr>
        <tr><th>価格</th><td>3,750万円</td></tr>
        <tr><th>土地面積</th><td>248.49m²</td></tr>
        <tr><th>建物面積</th><td>107.44m²</td></tr>
        <tr><th>間取り</th><td>4LDK</td></tr>
        <tr><th>建蔽率</th><td>50%</td></tr>
        <tr><th>容積率</th><td>80%</td></tr>
      </table>
    </body></html>
    """
    parser = AfrTochiParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(kodate_html, "lxml"))

    tochi_html = """
    <html><body>
      <h2>世田谷区売地</h2>
      <table>
        <tr><th>価格</th><td>8,000万円</td></tr>
        <tr><th>土地面積</th><td>120.00m²</td></tr>
        <tr><th>建蔽率</th><td>50%</td></tr>
        <tr><th>容積率</th><td>100%</td></tr>
      </table>
    </body></html>
    """
    item2 = parser.createEntity()
    result = parser._parsePropertyDetailPage(item2, BeautifulSoup(tochi_html, "lxml"))
    assert result.kenpeiStr == "50%"
    assert result.yousekiStr == "100%"


def test_afr_mansion_skips_ittou_apartment_1470():
    html = """
    <html><body>
      <h2>BLANC SQUARE</h2>
      <table>
        <tr><th>物件種別</th><td>一棟売アパート</td></tr>
        <tr><th>価格</th><td>12,000万円</td></tr>
        <tr><th>専有面積（最小）</th><td>40.00m²</td></tr>
      </table>
    </body></html>
    """
    parser = AfrMansionParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_daikyo_mansion_skips_ittou_mansion_1458():
    html = """
    <html><body>
      <h1>北区神谷２丁目一棟マンション（23,800万円）</h1>
      <table>
        <tr><th>価格</th><td>23,800万円</td></tr>
        <tr><th>専有面積</th><td>390.01m²</td></tr>
      </table>
    </body></html>
    """
    parser = DaikyoMansionParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_sekisui_mansion_skips_tochi_url_1450():
    html = "<html><body><h1>土地物件</h1></body></html>"
    parser = SekisuiMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://sumusite.sekisuihouse.co.jp/kanto/tochi/detail/C20010061635/"
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_sumai1_mansion_skips_inactive_library_page_1455():
    html = """
    <html><body>
      <h1>グランドメゾン品川シーサイドの杜</h1>
      <table>
        <tr><th>専有面積</th><td></td></tr>
        <tr><th>間取り</th><td></td></tr>
        <tr><th>築年月</th><td>2019年11月</td></tr>
      </table>
    </body></html>
    """
    parser = Sumai1MansionParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_rearie_mansion_skips_empty_ended_page_1468():
    html = "<html><head><title>- パナソニック ホームズ株式会社 - Panasonic</title></head><body></body></html>"
    parser = RearieMansionParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_misawa_mansion_skips_empty_ended_page_1447():
    html = "<html><head><title>ミサワホーム不動産の不動産検索</title></head><body></body></html>"
    parser = MisawaMansionParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_mitsui_mansion_and_invest_kodate_skip_ended_pages_1451_1453():
    html = "<html><body><h1>パークシティ中野</h1><div>このマンションに関連する物件</div></body></html>"
    m_parser = MitsuiMansionParser()
    m_item = m_parser.createEntity()
    m_item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/"
    with pytest.raises(SkipPropertyException):
        m_parser._parsePropertyDetailPage(m_item, BeautifulSoup(html, "lxml"))

    k_parser = MitsuiInvestmentKodateParser()
    k_item = k_parser.createEntity()
    k_item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/F8EBGA3E/"
    with pytest.raises(SkipPropertyException):
        k_parser._parsePropertyDetailPage(k_item, BeautifulSoup(html, "lxml"))


def test_athome_kodate_and_apartment_guards_1452_1463():
    k_parser = AthomeKodateParser()
    k_item = k_parser.createEntity()
    k_item.pageUrl = "https://www.athome.co.jp/mansion/1155089427"
    with pytest.raises(SkipPropertyException):
        k_parser._parsePropertyDetailPage(k_item, BeautifulSoup("<html><body></body></html>", "lxml"))

    a_parser = AthomeInvestmentApartmentParser()
    a_item = a_parser.createEntity()
    a_item.pageUrl = "https://www.athome.co.jp/buy_other/1198396219/"
    with pytest.raises(SkipPropertyException):
        a_parser._parsePropertyDetailPage(a_item, BeautifulSoup("<html><body><h1>売その他 5階</h1></body></html>", "lxml"))
