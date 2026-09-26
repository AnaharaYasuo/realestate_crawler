# -*- coding: utf-8 -*-
"""
住友不動産ステップ パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""

from package.parser.sumifuParser import (
    SumifuMansionParser,
    SumifuTochiParser,
    SumifuKodateParser,
    SumifuInvestmentKodateParser,
    SumifuInvestmentApartmentParser,
)
from package.models.sumifu import (
    SumifuMansion,
    SumifuTochi,
    SumifuKodate,
    SumifuInvestmentKodate,
    SumifuInvestmentApartment,
)

class TestSumifuParser:

    def test_create_entity(self):
        parser = SumifuMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuMansion)

    def test_create_entity_kodate(self):
        parser = SumifuKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuKodate)

    def test_create_entity_tochi(self):
        parser = SumifuTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuTochi)

    def test_create_entity_investment_apartment(self):
        parser = SumifuInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = SumifuInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuInvestmentKodate)

    def test_investment_charset_is_cp932(self):
        """住友不動産ステップ投資用物件はShift_JIS(CP932)のためgetCharset()がcp932を返すこと"""
        apt_parser = SumifuInvestmentApartmentParser(None)
        kodate_parser = SumifuInvestmentKodateParser(None)
        assert apt_parser.getCharset() == "cp932"
        assert kodate_parser.getCharset() == "cp932"

    def test_residential_charset_is_cp932(self):
        assert SumifuMansionParser(None).getCharset() == "cp932"
        assert SumifuKodateParser(None).getCharset() == "cp932"
        assert SumifuTochiParser(None).getCharset() == "cp932"

    def test_parser_configuration(self):
        parser = SumifuMansionParser(None)
        assert parser.__class__.__name__ == 'SumifuMansionParser'
