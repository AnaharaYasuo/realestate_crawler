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

    def test_parse_kanrihi_and_syuzen_labels(self):
        from bs4 import BeautifulSoup
        parser = MitsuiMansionParser(None)

        # Case 1: Labeled with 管理費 and 修繕積立金等
        html1 = """
        <table>
          <tr><th>管理費</th><td>12,300円/月</td></tr>
          <tr><th>修繕積立金等</th><td>8,500円/月</td></tr>
        </table>
        """
        soup1 = BeautifulSoup(html1, 'html.parser')
        assert parser._parseKanrihiStr(soup1) == '12,300円/月'
        assert parser._parseKanrihi(soup1) == 12300
        assert parser.get_management_fee_str(soup1) == '12,300円/月'
        assert parser.get_management_fee(soup1) == 12300

        assert parser._parseSyuzenTsumitateStr(soup1) == '8,500円/月'
        assert parser._parseSyuzenTsumitate(soup1) == 8500
        assert parser.get_reserve_fund_str(soup1) == '8,500円/月'
        assert parser.get_reserve_fund(soup1) == 8500

        # Case 2: Labeled with 管理費等 and 修繕積立金
        html2 = """
        <table>
          <tr><th>管理費等</th><td>15,000円</td></tr>
          <tr><th>修繕積立金</th><td>10,000円</td></tr>
        </table>
        """
        soup2 = BeautifulSoup(html2, 'html.parser')
        assert parser._parseKanrihiStr(soup2) == '15,000円'
        assert parser._parseKanrihi(soup2) == 15000
        assert parser._parseSyuzenTsumitateStr(soup2) == '10,000円'
        assert parser._parseSyuzenTsumitate(soup2) == 10000
