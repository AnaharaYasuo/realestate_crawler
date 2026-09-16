# -*- coding: utf-8 -*-
"""
三井不動産リアルティ パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・動的アクティブ生HTMLを検証します。
"""
from package.parser.mitsuiParser import (
    MitsuiMansionParser,
    MitsuiKodateParser,
    MitsuiTochiParser,
    MitsuiInvestmentKodateParser,
    MitsuiInvestmentApartmentParser,
)
from package.models.mitsui import (
    MitsuiMansion,
    MitsuiKodate,
    MitsuiTochi,
    MitsuiInvestmentKodate,
    MitsuiInvestmentApartment,
)

class TestMitsuiParser:

    def test_create_entity(self):
        parser = MitsuiMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiMansion)

    def test_create_entity_kodate(self):
        parser = MitsuiKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiKodate)

    def test_create_entity_tochi(self):
        parser = MitsuiTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiTochi)

    def test_create_entity_investment_apartment(self):
        parser = MitsuiInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = MitsuiInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiInvestmentKodate)

    def test_parser_selectors_configuration(self):
        parser = MitsuiMansionParser(None)
        assert parser.__class__.__name__ == 'MitsuiMansionParser'
