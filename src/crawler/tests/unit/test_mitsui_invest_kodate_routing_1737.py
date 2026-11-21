from package.parser.mitsuiParser import MitsuiInvestmentKodateParser
from package.utils.url_router import UrlRouter


def test_url_router_resolves_mitsui_invest_kodate_parser():
    parser = UrlRouter.create_parser(
        url="https://www.rehouse.co.jp/buy/kodate/bkdetail/FRMAWA0B/",
        property_type="invest_kodate",
    )
    assert isinstance(parser, MitsuiInvestmentKodateParser)
