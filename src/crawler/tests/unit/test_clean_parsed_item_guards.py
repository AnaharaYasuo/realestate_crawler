# -*- coding: utf-8 -*-
"""
clean_parsed_item 数値型・NOT NULL制約ガードおよび非物件リンク除外テスト
"""
from decimal import Decimal
import pytest
from bs4 import BeautifulSoup

from package.parser.sumifuParser import SumifuInvestmentApartmentParser
from package.models.sumifu import SumifuInvestmentApartment


class TestCleanParsedItemGuards:

    def test_annual_rent_null_guard(self):
        """NOT NULL制約の annualRent が None の場合、0 にサニタイズされること"""
        parser = SumifuInvestmentApartmentParser(None)
        item = SumifuInvestmentApartment()

        item.annualRent = None
        cleaned = parser.clean_parsed_item(item)
        assert cleaned.annualRent == 0

    def test_annual_rent_overflow_clamp(self):
        """21.4億円超の annualRent が 32-bit INT 最大値 (2147483647) に安全クランプされること"""
        parser = SumifuInvestmentApartmentParser(None)
        item = SumifuInvestmentApartment()
        item.annualRent = 2500000000  # 25億円
        cleaned = parser.clean_parsed_item(item)
        assert cleaned.annualRent == 2147483647

    def test_gross_yield_null_guard(self):
        """NOT NULL制約の grossYield が None の場合、Decimal('0.0') にサニタイズされること"""
        parser = SumifuInvestmentApartmentParser(None)
        item = SumifuInvestmentApartment()
        item.grossYield = None
        cleaned = parser.clean_parsed_item(item)
        assert cleaned.grossYield == Decimal('0.0')

    @pytest.mark.asyncio
    async def test_parse_page_core_link_filtering(self):
        """_parsePageCore が javascript:, mailto:, /inquiry/, /contact/ 等を除外すること"""
        parser = SumifuInvestmentApartmentParser(None)
        html = """
        <html>
            <body>
                <a href="javascript:void(0);">JS Link</a>
                <a href="mailto:info@example.com">Mail Link</a>
                <a href="tel:0312345678">Tel Link</a>
                <a href="#top">Anchor Link</a>
                <a href="https://example.com/inquiry/?id=123">Inquiry Link</a>
                <a href="https://example.com/contact/form">Contact Link</a>
                <a href="https://example.com/pro/detail_12345/">Valid Detail Link</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = [url async for url in parser._parsePageCore(soup, parser.getPropertyListXpath, parser.getPropertyListDestUrl)]
        assert len(urls) == 1
        assert urls[0] == "https://example.com/pro/detail_12345/"

    @pytest.mark.asyncio
    async def test_sumifu_investment_link_filtering(self):
        """SumifuInvestmentApartmentParser が問い合わせ・javascriptリンクを除外すること"""
        parser = SumifuInvestmentApartmentParser(None)
        html = """
        <html>
            <body>
                <a href="javascript:void(0);?limit=1000&mode=2">JS Pagination</a>
                <a href="/inquiry/?inq_type=471">Inquiry</a>
                <a href="/pro/detail_160D4015/">Property 1</a>
                <a href="/pro/detail_36214013/">Property 2</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = [url async for url in parser.parsePropertyListPage(soup)]
        assert len(urls) == 2
        assert all("/pro/detail_" in u for u in urls)
        assert not any("javascript" in u for u in urls)
        assert not any("inquiry" in u for u in urls)
