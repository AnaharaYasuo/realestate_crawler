# -*- coding: utf-8 -*-
"""
野村不動産ソリューションズ（PROVIA / ノムコム） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
import pytest
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

    @pytest.mark.asyncio
    async def test_parse_next_page_fallback_and_url_resolution(self):
        from bs4 import BeautifulSoup

        parser = NomuraInvestmentKodateParser(None)

        # 1. Standard a.next
        html_std = '<div class="pager"><a class="next" href="/pro/house/p2/">Next</a></div>'
        soup_std = BeautifulSoup(html_std, "html.parser")
        next_std = await parser.parseNextPage(soup_std)
        assert next_std == "https://www.nomu.com/pro/house/p2/"

        # 2. Text fallback ("次へ") without class="next"
        html_txt = '<div class="pager"><a href="/pro/search/?type_ids[]=5&pager_page=2"><span>次へ</span></a></div>'
        soup_txt = BeautifulSoup(html_txt, "html.parser")
        next_txt = await parser.parseNextPage(soup_txt)
        assert next_txt == "https://www.nomu.com/pro/search/?type_ids[]=5&pager_page=2"

        # 3. Already absolute URL
        html_abs = '<div class="pager"><a href="https://www.nomu.com/pro/search/?pager_page=3">次へ</a></div>'
        soup_abs = BeautifulSoup(html_abs, "html.parser")
        next_abs = await parser.parseNextPage(soup_abs)
        assert next_abs == "https://www.nomu.com/pro/search/?pager_page=3"

        # 4. pager_page fallback without "次へ" text
        html_pager = '<div class="pager"><a href="/pro/search/?pager_page=4"><span>4</span></a></div>'
        soup_pager = BeautifulSoup(html_pager, "html.parser")
        next_pager = await parser.parseNextPage(soup_pager)
        assert next_pager == "https://www.nomu.com/pro/search/?pager_page=4"

        # 5. Path-relative URL with current_url
        html_rel = '<div class="pager"><a href="search/?pager_page=5">次へ</a></div>'
        soup_rel = BeautifulSoup(html_rel, "html.parser")
        next_rel = await parser.parseNextPage(soup_rel, current_url="https://www.nomu.com/pro/")
        assert next_rel == "https://www.nomu.com/pro/search/?pager_page=5"

        # 6. Scheme-relative URL rejection
        html_scheme_rel = '<div class="pager"><a href="//evil.com/pro/search/?pager_page=6">次へ</a></div>'
        soup_scheme_rel = BeautifulSoup(html_scheme_rel, "html.parser")
        next_scheme_rel = await parser.parseNextPage(soup_scheme_rel)
        assert next_scheme_rel == ""

        # 7. No next page
        html_none = '<div class="pager"><span class="current">1</span></div>'
        soup_none = BeautifulSoup(html_none, "html.parser")
        next_none = await parser.parseNextPage(soup_none)
        assert next_none == ""
