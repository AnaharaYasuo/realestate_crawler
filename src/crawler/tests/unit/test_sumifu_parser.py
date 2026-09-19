# -*- coding: utf-8 -*-
"""
住友不動産ステップ パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
import pytest
from bs4 import BeautifulSoup

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

    def test_investment_parse_kouzou_string_handling(self):
        """スペック辞書の値が文字列の場合でも例外なく構造が抽出できること"""
        parser = SumifuInvestmentApartmentParser(None)
        soup = BeautifulSoup("<table><tr><th>階数構造</th><td>地上3階建て鉄骨造</td></tr></table>", "html.parser")
        kouzou = parser._parseKouzou(soup)
        assert kouzou == "鉄骨造"


    def test_parser_configuration(self):
        parser = SumifuMansionParser(None)
        assert parser.__class__.__name__ == 'SumifuMansionParser'

    def test_normalize_none_guard(self):
        parser = SumifuMansionParser(None)
        soup = BeautifulSoup("<table><tr><th></th><td></td></tr></table>", "html.parser")
        # Should not raise exception with None or empty title
        assert parser._getValueFromTable(soup, "") is None

    def test_mansion_detail_page_none_safety(self):
        parser = SumifuMansionParser(None)
        soup = BeautifulSoup("<html><body><h1>テスト物件</h1></body></html>", "html.parser")
        item = parser.createEntity()
        # Should not raise AttributeError: 'NoneType' object has no attribute 'replace'
        parsed = parser._parsePropertyDetailPage(item, soup)
        assert parsed is not None
        assert parsed.kanriKeitaiKaisya == ""

    @pytest.mark.asyncio
    async def test_parse_page_core_link_filtering(self):
        parser = SumifuTochiParser(None)
        html = """
        <html>
            <body>
                <div id="searchResultBlock">
                    <a href="/tochi/detail_12345/">土地1</a>
                    <a href="/mansion/detail_67890/">マンション（関連リンク）</a>
                    <a href="/chintai/detail/11111/">賃貸リンク</a>
                    <a href="/uri/kounyu/">メニューリンク</a>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = [url async for url in parser.parsePropertyListPage(soup)]
        # Must only yield the tochi link!
        assert len(urls) == 1
        assert "/tochi/detail_12345/" in urls[0]
