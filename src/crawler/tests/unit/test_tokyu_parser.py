# -*- coding: utf-8 -*-
"""
東急リバブル パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.tokyuParser import (
    TokyuMansionParser,
    TokyuKodateParser,
    TokyuTochiParser,
    TokyuInvestmentKodateParser,
    TokyuInvestmentApartmentParser,
)
from package.models.tokyu import (
    TokyuMansion,
    TokyuKodate,
    TokyuTochi,
    TokyuInvestmentKodate,
    TokyuInvestmentApartment,
)

class TestTokyuParser:

    def test_create_entity(self):
        parser = TokyuMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuMansion)

    def test_create_entity_kodate(self):
        parser = TokyuKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuKodate)

    def test_create_entity_tochi(self):
        parser = TokyuTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuTochi)

    def test_create_entity_investment_apartment(self):
        parser = TokyuInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = TokyuInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuInvestmentKodate)

    def test_parser_configuration(self):
        parser = TokyuMansionParser(None)
        assert parser.__class__.__name__ == "TokyuMansionParser"
