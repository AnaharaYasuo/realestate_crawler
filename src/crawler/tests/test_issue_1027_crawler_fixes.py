from bs4 import BeautifulSoup
from unittest.mock import MagicMock
from package.parser.heimParser import HeimKodateParser
from package.parser.baseParser import ParserBase
from package.models.mitsui import MitsuiInvestmentKodate


def test_heim_label_regex_grouping():
    parser = HeimKodateParser()
    html = '<table class="planTblWrap"><tr><th>種別 土地</th><td>価格 5,000万円</td><td>土地面積 120.5m2</td></tr></table>'
    soup = BeautifulSoup(html, "html.parser")
    specs = {}
    parser._heim_specs_from_plan_tbl(soup, specs)
    assert specs.get("種別") == "土地"
    assert specs.get("価格") == "5,000万円"
    assert specs.get("土地面積") == "120.5m2"


def test_validation_switched_from_residential_to_investment():
    parser = MagicMock(spec=ParserBase)
    parser.EXPECTED_SPEC_FIELDS_BY_TYPE = ParserBase.EXPECTED_SPEC_FIELDS_BY_TYPE
    parser._resolve_validation_property_type = lambda item: "investment"
    parser._validate_item_field = lambda item, field: None

    item = MitsuiInvestmentKodate()
    item.price = 5000
    item.address = "東京都新宿区"
    item.kouzou = "木造"
    item.grossYield = None
    item.annualRent = None
    item._switched_from_property_type = "kodate"

    # Call unbound validate_extracted_fields
    errors = ParserBase.validate_extracted_fields(parser, item)
    err_fields = [e["field"] for e in errors]
    assert "grossYield" not in err_fields
    assert "annualRent" not in err_fields
