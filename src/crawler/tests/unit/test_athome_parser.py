# -*- coding: utf-8 -*-
"""
アットホーム（Athome） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.athomeParser import AthomeMansionParser, AthomeKodateParser, AthomeInvestmentApartmentParser, AthomeTochiParser
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment, AthomeTochi
from bs4 import BeautifulSoup

def test_athome_mansion_parser():
    parser = AthomeMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeMansion)

def test_athome_kodate_parser():
    parser = AthomeKodateParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeKodate)

def test_athome_investment_apartment_parser():
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeInvestmentApartment)

def test_athome_tochi_parser():
    parser = AthomeTochiParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeTochi)

def test_athome_price_extraction():
    parser = AthomeTochiParser()
    # Test th/td match
    soup1 = BeautifulSoup("<table><tr><th>価格</th><td>3,580万円</td></tr></table>", "html.parser")
    assert parser._parsePriceStr(soup1) == "3,580万円"
    assert parser._parsePrice(soup1) == 35800000

    # Test specs table match
    specs = {"販売価格": "4,200万円"}
    soup2 = BeautifulSoup("<div><p>物件詳細</p></div>", "html.parser")
    assert parser._parsePriceStr(soup2, specs) == "4,200万円"
    assert parser._parsePrice(soup2, specs) == 42000000

    # Test class-based fallback (.bukken-price)
    soup3 = BeautifulSoup("<div class='bukken-price'>5,180万円</div>", "html.parser")
    assert parser._parsePriceStr(soup3) == "5,180万円"
    assert parser._parsePrice(soup3) == 51800000


def test_athome_url_resolution():
    parser = AthomeKodateParser()
    base = "https://www.athome.co.jp/kodate/chuko/tokyo/tokyo_fuchu-city/list/"
    rel_url = "/kodate/1012790620/?DOWN=1&BKLISTID=001LPC"
    resolved = parser.getRootDestUrl(rel_url, base_domain=base)
    assert resolved == "https://www.athome.co.jp/kodate/1012790620/?DOWN=1&BKLISTID=001LPC"
    assert "//kodate" not in resolved
    assert "/list//kodate" not in resolved


def test_athome_detail_path_filtering():
    parser = AthomeKodateParser()
    # Kodate parser should accept kodate details
    assert parser._is_athome_detail_path("/kodate/12345678/", "https://www.athome.co.jp/kodate/12345678/")
    # Kodate parser should reject recommendation links
    assert not parser._is_athome_detail_path("/kodate/12345678/", "https://www.athome.co.jp/kodate/12345678/?RECOMMFLG=1")
    assert not parser._is_athome_detail_path("/kodate/12345678/", "https://www.athome.co.jp/kodate/12345678/?sref=nw_reco")
    # Kodate parser should reject investment/apartment detail paths
    assert not parser._is_athome_detail_path("/buy_other/1113105018/", "https://www.athome.co.jp/buy_other/1113105018/")
