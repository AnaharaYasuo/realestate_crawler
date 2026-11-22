from unittest.mock import patch

from bs4 import BeautifulSoup
from package.parser.tokyuParser import TokyuInvestmentApartmentParser, TokyuInvestmentKodateParser
from package.utils.url_router import UrlRouter


def test_url_router_resolves_tokyu_invest_kodate_parser():
    parser = UrlRouter.create_parser(
        url="https://www.livable.co.jp/kodate/C13269K70/",
        property_type="invest_kodate",
    )
    assert isinstance(parser, TokyuInvestmentKodateParser)


def test_fudosan_toushi_does_not_switch_to_mansion_parser():
    parser = TokyuInvestmentApartmentParser()
    item = parser.createEntity()
    soup = BeautifulSoup("<html><head><title>投資マンション</title></head><body></body></html>", "html.parser")
    with patch(
        "package.utils.property_type_detector.PropertyTypeDetector.detect",
        return_value="mansion",
    ):
        resolved_parser, _ = parser._maybe_switch_parser(
            url="https://www.livable.co.jp/fudosan-toushi/C13269K70/",
            title="投資マンション",
            soup=soup,
            specs={},
            item=item,
        )
    assert resolved_parser is parser
