# -*- coding: utf-8 -*-
"""Odakyu investment detail URL normalization (Issue #317): keep /mansion/detail/ prefix."""
import asyncio
from bs4 import BeautifulSoup
from package.parser.odakyuParser import OdakyuInvestmentParser


def test_odakyu_investment_normalize_keeps_type_prefix():
    parser = OdakyuInvestmentParser()
    href = "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/"
    assert parser._normalize_detail_url(href) == (
        "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/"
    )


def test_odakyu_investment_normalize_rejects_bare_detail_path():
    parser = OdakyuInvestmentParser()
    assert parser._normalize_detail_url(
        "https://www.odakyu-chukai.com/detail/B01419-001363/"
    ) is None


def test_odakyu_investment_parse_root_yields_prefixed_urls():
    html = """
    <html><body>
      <a href="https://www.odakyu-chukai.com/mansion/detail/B01419-001363/">A</a>
      <a href="/house/detail/H123/">B</a>
      <a href="/detail/BAD/">C</a>
    </body></html>
    """
    parser = OdakyuInvestmentParser()
    soup = BeautifulSoup(html, "html.parser")

    async def collect():
        return [u async for u in parser.parseRootPage(soup)]

    links = asyncio.run(collect())
    assert "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/" in links
    assert "https://www.odakyu-chukai.com/house/detail/H123/" in links
    assert all("/detail/BAD" not in u for u in links)
