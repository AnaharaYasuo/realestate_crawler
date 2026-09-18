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
