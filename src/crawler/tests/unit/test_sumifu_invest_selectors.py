from package.utils.selector_loader import SelectorLoader
from package.parser.sumifuParser import (
    SumifuInvestmentKodateParser,
    SumifuInvestmentApartmentParser,
)


def test_sumifu_invest_selectors_loaded():
    """Verify sumifu.yaml contains invest_kodate and invest_apartment and loads without KeyError."""
    kodate_sel = SelectorLoader.load("sumifu", "invest_kodate")
    assert kodate_sel is not None
    assert "property_links" in kodate_sel
    assert kodate_sel["property_links"] == "a[href*='/pro/detail_']"

    apt_sel = SelectorLoader.load("sumifu", "invest_apartment")
    assert apt_sel is not None
    assert "property_links" in apt_sel
    assert apt_sel["property_links"] == "a[href*='/pro/detail_']"


def test_sumifu_investment_kodate_parser_init():
    """Verify SumifuInvestmentKodateParser instantiates with invest_kodate property type."""
    parser = SumifuInvestmentKodateParser("")
    assert parser.property_type == "invest_kodate"
    assert parser.selectors is not None
    entity = parser.createEntity()
    assert entity.__class__.__name__ == "SumifuInvestmentKodate"


def test_sumifu_investment_apartment_parser_init():
    """Verify SumifuInvestmentApartmentParser instantiates with invest_apartment property type."""
    parser = SumifuInvestmentApartmentParser("")
    assert parser.property_type == "invest_apartment"
    assert parser.selectors is not None
    entity = parser.createEntity()
    assert entity.__class__.__name__ == "SumifuInvestmentApartment"
