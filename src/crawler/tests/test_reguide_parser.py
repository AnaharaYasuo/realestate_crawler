# -*- coding: utf-8 -*-
from decimal import Decimal
import os
import pytest
from bs4 import BeautifulSoup
from package.parser.reguideParser import ReguideInvestmentParser

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "reguide_investment_sample.html"
)


@pytest.fixture
def sample_soup():
    assert os.path.exists(FIXTURE_PATH), f"Fixture not found at {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="euc-jp", errors="ignore") as f:
        html = f.read()
    return BeautifulSoup(html, "html.parser")


def test_reguide_investment_parser_mandatory_methods():
    parser = ReguideInvestmentParser()
    mandatory_methods = [
        "_parsePrice",
        "_parsePriceStr",
        "_parseAddress",
        "_parsePropertyName",
        "_parseTransport1",
        "_parseGrossYield",
        "_parseAnnualRent",
        "_parseChikunengetsu",
        "_parseKouzou",
        "_parseTochiMenseki",
        "_parseTatemonoMenseki",
    ]
    for method_name in mandatory_methods:
        assert hasattr(parser, method_name), f"Missing method {method_name}"
        assert callable(getattr(parser, method_name))


def test_reguide_investment_parser_extract_specs(sample_soup):
    parser = ReguideInvestmentParser()
    specs = parser._get_specs(sample_soup)
    assert len(specs) > 0

    # 価格
    price = parser._parsePrice(sample_soup, specs)
    price_str = parser._parsePriceStr(sample_soup, specs)
    assert price == 7380000
    assert price_str == "738万円"

    # 表面利回り & 満室想定年間収入
    yield_val = parser._parseGrossYield(sample_soup, specs)
    annual_rent = parser._parseAnnualRent(sample_soup, specs)
    assert yield_val == Decimal("8.61")
    assert annual_rent == 636000

    # 所在地
    address = parser._parseAddress(sample_soup, specs)
    assert address == "東京都杉並区井草2-1-2"

    # 物件名
    name = parser._parsePropertyName(sample_soup, specs)
    assert name == "サンパレス井草"


def test_reguide_investment_parser_extract_detail_urls():
    parser = ReguideInvestmentParser()
    sample_list_html = """
    <ul id="result_list">
        <li>
            <a href="/investment/421139/">プレール・ドゥーク東京EAST</a>
        </li>
        <li>
            <a href="/investment/421140/">ライオンズマンション</a>
        </li>
    </ul>
    """
    urls = parser.extract_detail_urls(sample_list_html)
    assert len(urls) == 2
    assert "https://re-guide.jp/investment/421139/" in urls
    assert "https://re-guide.jp/investment/421140/" in urls


@pytest.mark.asyncio
async def test_reguide_investment_parser_parse_next_page():
    parser = ReguideInvestmentParser()
    # 1. Page 1 -> next is Page 2
    html_p1 = """
    <ul class="pager">
        <li><a href="/investment/list/?pager[p]=1">最初</a></li>
        <li>[1]</li>
        <li><a href="/investment/list/?pager[p]=2">[2]</a></li>
        <li><a href="/investment/list/?pager[p]=3">[3]</a></li>
        <li><a href="/investment/list/?pager[p]=86">最後</a></li>
    </ul>
    """
    soup1 = BeautifulSoup(html_p1, "html.parser")
    next_url1 = await parser.parseNextPage(soup1)
    assert next_url1 == "https://re-guide.jp/investment/list/?pager[p]=2"

    # 2. Page 2 -> next is Page 3
    html_p2 = """
    <ul class="pager">
        <li><a href="/investment/list/?pager[p]=1">最初</a></li>
        <li><a href="/investment/list/?pager[p]=1">[1]</a></li>
        <li>[2]</li>
        <li><a href="/investment/list/?pager[p]=3">[3]</a></li>
        <li><a href="/investment/list/?pager[p]=86">最後</a></li>
    </ul>
    """
    soup2 = BeautifulSoup(html_p2, "html.parser")
    next_url2 = await parser.parseNextPage(soup2)
    assert next_url2 == "https://re-guide.jp/investment/list/?pager[p]=3"

    # 3. Last Page 86 -> No next page
    html_last = """
    <ul class="pager">
        <li><a href="/investment/list/?pager[p]=1">最初</a></li>
        <li><a href="/investment/list/?pager[p]=85">[85]</a></li>
        <li>[86]</li>
    </ul>
    """
    soup_last = BeautifulSoup(html_last, "html.parser")
    next_url_last = await parser.parseNextPage(soup_last)
    assert next_url_last == ""


@pytest.mark.asyncio
async def test_reguide_investment_parser_parse_root_page():
    parser = ReguideInvestmentParser()
    sample_list_html = """
    <ul id="result_list">
        <li><a href="/investment/421139/">物件1</a></li>
        <li><a href="/investment/421140/">物件2</a></li>
    </ul>
    """
    soup = BeautifulSoup(sample_list_html, "html.parser")
    items = []
    async for item in parser.parseRootPage(soup):
        items.append(item)
    assert len(items) == 2
    assert items[0].url == "https://re-guide.jp/investment/421139/"
    assert items[1].url == "https://re-guide.jp/investment/421140/"


def test_reguide_investment_parser_create_entity_and_detail_mapping(sample_soup):
    parser = ReguideInvestmentParser()
    entity = parser.createEntity()
    assert entity is not None
    assert entity._meta.db_table == "reguide_investment"

    item = parser._parsePropertyDetailPage(entity, sample_soup)
    assert item.propertyName == "サンパレス井草"
    assert item.price == 7380000
    assert item.grossYield == Decimal("8.61")
    assert item.annualRent == 636000
    assert item.address == "東京都杉並区井草2-1-2"
    assert item.kouzou == "RC造"

