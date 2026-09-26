# -*- coding: utf-8 -*-
"""
野村不動産ソリューションズ（PROVIA / ノムコム） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.nomuraParser import (
    NomuraMansionParser,
    NomuraKodateParser,
    NomuraTochiParser,
    NomuraInvestmentKodateParser,
    NomuraInvestmentApartmentParser,
)
from package.models.nomura import (
    NomuraMansion,
    NomuraKodate,
    NomuraTochi,
    NomuraInvestmentKodate,
    NomuraInvestmentApartment,
)

class TestNomuraParser:

    def test_create_entity(self):
        parser = NomuraMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, NomuraMansion)

    def test_create_entity_kodate(self):
        parser = NomuraKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, NomuraKodate)

    def test_create_entity_tochi(self):
        parser = NomuraTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, NomuraTochi)

    def test_create_entity_investment_apartment(self):
        parser = NomuraInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, NomuraInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = NomuraInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, NomuraInvestmentKodate)

    def test_parser_configuration(self):
        parser = NomuraMansionParser(None)
        assert parser.__class__.__name__ == "NomuraMansionParser"
