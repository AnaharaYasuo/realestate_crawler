from bs4 import BeautifulSoup
from package.parser.homesParser import HomesInvestmentApartmentParser


def test_homes_invest_missing_annual_rent_does_not_skip():
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    item.price = 50000000
    item.grossYield = None
    soup = BeautifulSoup("<html><body><table></table></body></html>", "html.parser")
    parser._homes_parse_invest_rent(item, soup)
    assert item.annualRent is None or item.annualRent == 0
