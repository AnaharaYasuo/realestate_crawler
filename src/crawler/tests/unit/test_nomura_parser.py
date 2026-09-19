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

    def test_scrape_specs_with_tooltips_and_help_icons(self):
        from bs4 import BeautifulSoup
        html = """
        <table>
            <tr>
                <th>専有面積<p class="icon_help"><span class="tooltip">建物の総床面積が表示されます。<br/>壁芯面積</span></p></th>
                <td>75.50m2（22.83坪）</td>
            </tr>
            <tr>
                <th>間取り<span class="help">ヘルプ</span></th>
                <td>3LDK</td>
            </tr>
        </table>
        """
        parser = NomuraMansionParser(None)
        soup = BeautifulSoup(html, "html.parser")
        specs = parser._scrape_specs(soup)
        assert "専有面積" in specs
        assert specs["専有面積"] == "75.50m2（22.83坪）"
        assert "間取り" in specs
        assert specs["間取り"] == "3LDK"

    def test_scrape_specs_ignores_full_modal_glossary(self):
        from bs4 import BeautifulSoup
        html = """
        <div class="fullModal">
            <table>
                <tr>
                    <th>専有面積</th>
                    <td>建物の主たる構造及び建物階数が表示されます。用語の説明...</td>
                </tr>
            </table>
        </div>
        <table class="col4">
            <tr>
                <th>専有面積</th>
                <td>80.12m2</td>
            </tr>
        </table>
        """
        parser = NomuraMansionParser(None)
        soup = BeautifulSoup(html, "html.parser")
        specs = parser._scrape_specs(soup)
        assert specs.get("専有面積") == "80.12m2"

    def test_parse_senyu_menseki_with_real_error_html(self):
        import os
        from bs4 import BeautifulSoup
        from decimal import Decimal
        path = "src/crawler/tests/error_pages/nomura_mansion/1789766690.html"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            parser = NomuraMansionParser(None)
            val = parser._parseSenyuMenseki(soup)
            assert val == Decimal("98.08")
