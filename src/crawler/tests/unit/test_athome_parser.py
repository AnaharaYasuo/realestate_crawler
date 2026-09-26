# -*- coding: utf-8 -*-
"""
アットホーム（Athome） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.athomeParser import AthomeMansionParser, AthomeKodateParser, AthomeInvestmentApartmentParser
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment

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


def test_athome_kodate_skips_non_kodate():
    import pytest
    from bs4 import BeautifulSoup
    from package.parser.baseParser import SkipPropertyException

    parser = AthomeKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/buy_other/1113105018/?BKLISTID=031PPC"
    soup = BeautifulSoup("<div id='detailTitleArea'><h2><em>一棟売アパート</em></h2></div>", "html.parser")
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, soup)
