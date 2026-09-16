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
