from bs4 import BeautifulSoup
from package.parser.heimParser import HeimMansionParser, HeimKodateParser, HeimTochiParser
from package.models.heim import HeimMansion, HeimKodate, HeimTochi


def test_heim_parser_creation():
    assert isinstance(HeimMansionParser().createEntity(), HeimMansion)
    assert isinstance(HeimKodateParser().createEntity(), HeimKodate)
    assert isinstance(HeimTochiParser().createEntity(), HeimTochi)


def test_heim_mansion_no_forced_fallbacks_when_missing():
    parser = HeimMansionParser()
    soup = BeautifulSoup("<div></div>", "html.parser")
    # Empty specs: kouzou and chikunengetsuStr must be empty, not force-filled
    assert parser._parseKouzou(soup, specs={}) == ""
    assert parser._parseChikunengetsuStr(soup, specs={}) == ""
    assert parser._parseChikunengetsu(soup, specs={}) is None

    # Status strings must NOT be used as completion dates
    specs_with_status_only = {
        "現況": "空家",
        "引渡時期": "相談",
        "現状": "更地",
    }
    assert parser._parseChikunengetsuStr(soup, specs=specs_with_status_only) == ""
    assert parser._parseChikunengetsu(soup, specs=specs_with_status_only) is None


def test_heim_kodate_no_forced_fallbacks_when_missing():
    parser = HeimKodateParser()
    soup = BeautifulSoup("<div></div>", "html.parser")
    assert parser._parseKouzou(soup, specs={}) == ""
    assert parser._parseChikunengetsuStr(soup, specs={}) == ""
    assert parser._parseChikunengetsu(soup, specs={}) is None

    specs_with_status_only = {
        "現況": "完成済",
        "引渡時期": "即時",
    }
    assert parser._parseChikunengetsuStr(soup, specs=specs_with_status_only) == ""


def test_heim_legitimate_keys_extracted():
    parser = HeimMansionParser()
    soup = BeautifulSoup("<div></div>", "html.parser")
    # Legitimate synonyms for structure
    assert parser._parseKouzou(soup, specs={"構造": "RC造"}) == "RC造"
    assert parser._parseKouzou(soup, specs={"建物構造": "鉄骨造"}) == "鉄骨造"

    # Legitimate completion dates
    assert parser._parseChikunengetsuStr(soup, specs={"築年月": "2020年3月"}) == "2020年3月"
    assert parser._parseChikunengetsuStr(soup, specs={"完成年月": "2024年1月"}) == "2024年1月"
    assert parser._parseChikunengetsuStr(soup, specs={"完成時期": "2025年6月"}) == "2025年6月"
