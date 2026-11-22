from package.parser.athomeParser import AthomeKodateParser
from package.utils.url_router import UrlRouter


def test_url_router_resolves_athome_invest_kodate_parser():
    parser = UrlRouter.create_parser(
        url="https://www.athome.co.jp/kodate/1234567890/",
        property_type="invest_kodate",
    )
    assert isinstance(parser, AthomeKodateParser)
