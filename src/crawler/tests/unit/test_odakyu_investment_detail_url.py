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
      <div class="estate-block">
        <input type="checkbox" name="ids[]" value="VI0023"/>
        <p class="estate-info-catch">【オーナーチェンジ物件】利回り16.76％</p>
        <p class="estate-price-item"><strong>680</strong>万円</p>
        <dl class="address"><dt>所在地</dt><dd>坂東市辺田</dd></dl>
        <h2 class="estate-block-name"><a href="//detail/VI0023//">ロジュマン</a></h2>
      </div>
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
    assert any("focus=VI0023" in u for u in links)
    assert "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/" in links
    assert "https://www.odakyu-chukai.com/house/detail/H123/" in links
    assert all("/detail/BAD" not in u for u in links)


def test_odakyu_investment_list_card_parses_yield_and_derived_rent():
    html = """
    <html><body>
      <div class="estate-block">
        <input type="checkbox" name="ids[]" value="VI0023"/>
        <p class="estate-info-catch">【オーナーチェンジ物件】利回り16.76％戸建賃貸</p>
        <p class="estate-price-item"><strong>680</strong>万円</p>
        <div class="estate-info-list">
          <dl class="address"><dt>所在地</dt><dd>坂東市辺田</dd></dl>
        </div>
        <h2 class="estate-block-name"><a href="//detail/VI0023//">ロジュマン坂東市辺田</a></h2>
      </div>
    </body></html>
    """
    parser = OdakyuInvestmentParser()
    soup = BeautifulSoup(html, "html.parser")
    item = parser.createEntity()
    item.pageUrl = "https://www.odakyu-chukai.com/invest/list/?focus=VI0023"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.propertyName.startswith("ロジュマン")
    assert item.price and item.price > 0
    assert item.address
    assert item.grossYield and float(item.grossYield) > 0
    assert item.annualRent and item.annualRent > 0
