"""Unit tests for Issue #1794: reduce transient_skipped in TTL recrawl.

1. baseParser._maybe_switch_parser:
   Allow kodate -> invest_kodate to stay on self when UrlRouter maps invest_kodate
   to the same KodateParser class (instead of raising IncompatiblePropertyTypeException).
2. HomesInvestmentApartmentParser:
   Raise ListingEndedException when toushi.homes.co.jp redirects to the member login page.
"""

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from package.parser.athomeParser import AthomeKodateParser, AthomeMansionParser
from package.parser.baseParser import IncompatiblePropertyTypeException, ListingEndedException
from package.parser.homesParser import HomesInvestmentApartmentParser


def test_kodate_to_invest_kodate_same_parser_continues_without_error():
    parser = AthomeKodateParser()
    item = parser.createEntity()
    url = "https://www.athome.co.jp/kodate/1076537447/"
    soup = BeautifulSoup("<html><head><title>オーナーチェンジ戸建</title></head><body>利回り 8.5%</body></html>", "html.parser")

    with (
        patch("package.parser.baseParser.PropertyTypeDetector.detect", return_value="invest_kodate"),
        patch("package.parser.baseParser.UrlRouter.create_parser", return_value=AthomeKodateParser()),
    ):
        resolved_parser, resolved_item = parser._maybe_switch_parser(
            url=url,
            title="オーナーチェンジ戸建",
            soup=soup,
            specs={},
            item=item,
        )

    assert resolved_parser is parser
    assert resolved_item is item


def test_mansion_to_apartment_same_parser_still_raises_incompatible():
    parser = AthomeMansionParser()
    item = parser.createEntity()
    url = "https://www.athome.co.jp/mansion/1234567890/"
    soup = BeautifulSoup("<html><head><title>一棟アパート</title></head><body>一棟売アパート</body></html>", "html.parser")

    with (
        patch("package.parser.baseParser.PropertyTypeDetector.detect", return_value="apartment"),
        patch("package.parser.baseParser.UrlRouter.create_parser", return_value=AthomeMansionParser()),
    ):
        with pytest.raises(IncompatiblePropertyTypeException):
            parser._maybe_switch_parser(
                url=url,
                title="一棟アパート",
                soup=soup,
                specs={},
                item=item,
            )


def test_homes_investment_login_redirect_raises_listing_ended():
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://toushi.homes.co.jp/bukkendetail/index/4723986/"
    html = """
    <html>
      <head><title>【ホームズ】マイページログイン｜不動産投資で資産運用</title></head>
      <body><h1>マイページログイン</h1><form action="/login"></form></body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)
