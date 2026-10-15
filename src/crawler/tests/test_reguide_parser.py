# -*- coding: utf-8 -*-
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
    assert yield_val == 8.61
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
