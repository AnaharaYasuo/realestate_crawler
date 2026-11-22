import pytest
from bs4 import BeautifulSoup
from package.parser.baseParser import SkipPropertyException
from package.parser.mitsuiParser import MitsuiKodateParser, MitsuiTochiParser


def test_mitsui_tochi_parser_skips_kodate_url_when_not_switched():
    parser = MitsuiTochiParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/FN3BRA06/"
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    with pytest.raises(SkipPropertyException, match="Non-tochi URL"):
        parser._parsePropertyDetailPage(item, soup)


def test_mitsui_kodate_parser_allows_tochi_url_when_switched():
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FSX4QA0B/"
    item._switched_from_property_type = "tochi"
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    # Should not raise "Non-kodate URL in MitsuiKodateParser"
    with pytest.raises(SkipPropertyException) as exc_info:
        parser._parsePropertyDetailPage(item, soup)
    assert "Non-kodate URL" not in str(exc_info.value)
