from package.parser.reguideParser import ReguideInvestmentParser
from routes.reguide_routes import REGUIDE_INVESTMENT_ROOT_URL, REGUIDE_DETAIL_URL_PATTERN

def test_reguide_urls_and_validation():
    parser = ReguideInvestmentParser()
    assert parser.BASE_URL == "https://www.re-guide.jp"
    assert REGUIDE_INVESTMENT_ROOT_URL == "https://www.re-guide.jp/investment/list/"

    # Check valid URLs
    valid_detail_1 = "https://www.re-guide.jp/investment/12345/"
    valid_detail_2 = "https://re-guide.jp/investment/12345/"
    assert parser._is_valid_reguide_url(valid_detail_1) is True
    assert parser._is_valid_reguide_url(valid_detail_2) is True
    assert bool(REGUIDE_DETAIL_URL_PATTERN.match(valid_detail_1)) is True
    assert bool(REGUIDE_DETAIL_URL_PATTERN.match(valid_detail_2)) is True

    # Invalid URL
    invalid_url = "https://example.com/investment/12345/"
    assert parser._is_valid_reguide_url(invalid_url) is False
    assert bool(REGUIDE_DETAIL_URL_PATTERN.match(invalid_url)) is False
