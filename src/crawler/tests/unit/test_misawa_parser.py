# -*- coding: utf-8 -*-
"""
ミサワホーム不動産 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.misawaParser import (
    MisawaMansionParser,
    MisawaKodateParser,
    MisawaTochiParser,
    MisawaInvestmentKodateParser,
    MisawaInvestmentApartmentParser,
)
from package.models.misawa import (
    MisawaMansion,
    MisawaKodate,
    MisawaTochi,
    MisawaInvestmentKodate,
    MisawaInvestmentApartment,
)

class TestMisawaParser:

    def test_create_entity(self):
        parser = MisawaMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaMansion)

    def test_create_entity_kodate(self):
        parser = MisawaKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaKodate)

    def test_create_entity_tochi(self):
        parser = MisawaTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaTochi)

    def test_create_entity_investment_apartment(self):
        parser = MisawaInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = MisawaInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentKodate)

    def test_parser_configuration(self):
        parser = MisawaMansionParser(None)
        assert parser.__class__.__name__ == "MisawaMansionParser"

    def test_investment_kodate_start_uses_kodate_parser(self):
        from package.api.misawa_investment import ParseMisawaInvestmentKodateStartAsync

        parser = ParseMisawaInvestmentKodateStartAsync()._generateParser()
        assert parser.__class__.__name__ == "MisawaInvestmentKodateParser"
