from bs4 import BeautifulSoup

from package.parser.misawaParser import (
    MisawaKodateParser,
    MisawaInvestmentApartmentParser,
)
from package.parser.mitsuiParser import (
    MitsuiMansionParser,
    MitsuiKodateParser,
    MitsuiTochiParser,
)
from package.parser.nomuraParser import (
    NomuraKodateParser,
    NomuraTochiParser,
    NomuraInvestmentApartmentParser,
)
from package.parser.sumifuParser import (
    SumifuMansionParser,
    SumifuKodateParser,
    SumifuTochiParser,
    SumifuInvestmentApartmentParser,
)
from package.parser.tokyuParser import (
    TokyuKodateParser,
    TokyuTochiParser,
)


def test_misawa_no_dummy_fallbacks():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    empty_specs = {}

    kodate = MisawaKodateParser()
    assert kodate._parseNeighborhood(soup, empty_specs) == ""
    assert kodate._parseSchoolDistrict(soup, empty_specs) == ""
    assert kodate._parseTransactionType(soup, empty_specs) == ""
    assert kodate._parseUrbanPlanning(soup, empty_specs) == ""
    assert kodate._parseKakuninBango(soup, empty_specs) == ""
    assert kodate._parseSetback(soup, empty_specs) == ""
    assert kodate._parseBiko(soup, empty_specs) == ""
    assert kodate._parsePrivateRoadFee(soup, empty_specs) == ""

    invest = MisawaInvestmentApartmentParser()
    assert invest._parseTochikenri_I(soup, empty_specs) == ""
    assert invest._parseDeliveryDate_I(soup, empty_specs) == ""
    assert invest._parseTransactionType_I(soup, empty_specs) == ""


def test_mitsui_no_dummy_fallbacks():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    empty_specs = {}

    mansion = MitsuiMansionParser()
    assert mansion._parseKouzou(soup, empty_specs) == ""
    assert mansion._parseKanriKeitaiKaisya(soup, empty_specs) == ""
    assert mansion._parseSaikouKadobeya(soup, empty_specs) == ""

    kodate = MitsuiKodateParser()
    assert kodate._parseKouzouFromKaisuKouzou("-") == ""

    tochi = MitsuiTochiParser()
    assert tochi._parseKenchikuJoken(soup, empty_specs) == ""
    assert tochi._parseChimoku(soup, empty_specs) == ""
    assert tochi._parseYoutoChiiki(soup, empty_specs) == ""
    assert tochi._parseKuiki(soup, empty_specs) == ""
    assert tochi._parseKokudoHou(soup, empty_specs) == ""
    details = tochi._parseSetudouDetails("")
    assert details["douroKubun"] == ""
    assert details["douroMuki"] == ""


def test_nomura_no_dummy_fallbacks():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    empty_specs = {}

    kodate = NomuraKodateParser()
    assert kodate._parseCurrentStatus(soup, empty_specs) == ""
    assert kodate._parseHikiwatashi(soup, empty_specs) == ""
    assert kodate._parseTorihiki(soup, empty_specs) == ""

    tochi = NomuraTochiParser()
    item = tochi.createEntity()
    item = tochi._parsePropertyDetailPage(item, soup)
    assert getattr(item, "kaisuStr", None) == ""

    invest = NomuraInvestmentApartmentParser()
    assert invest._parseHikiwatashiInvest(soup, empty_specs) == ""
    assert invest._parseTorihikiInvest(soup, empty_specs) == ""
    assert invest._parseKouzouInvest(soup, empty_specs) == ""


def test_sumifu_no_dummy_fallbacks():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    empty_specs = {}

    mansion = SumifuMansionParser()
    assert mansion._parseChiikiChiku(soup, empty_specs) == ""
    assert mansion._parseBoukaChiiki(soup, empty_specs) == ""
    assert mansion._parseSonotaChiiki(soup, empty_specs) == ""
    assert mansion._parseMadori(soup, empty_specs) == ""
    assert mansion._parseChikunengetsuStr(soup, empty_specs) == ""
    assert mansion._parseSaikou(soup, empty_specs) == ""
    assert mansion._parseKadobeya(soup, empty_specs) == ""
    assert mansion._parseKanriKeitai(soup, empty_specs) == ""
    assert mansion._parseKanriKaisya(soup, empty_specs) == ""
    assert mansion._parseKaisuStr(soup, empty_specs) == ""

    kodate = SumifuKodateParser()
    assert kodate._parseKaisuKouzou(soup, empty_specs) == ""
    assert kodate._parseKouzou(soup, empty_specs) == ""
    assert kodate._parseChimoku(soup, empty_specs) == ""
    assert kodate._parseChisei(soup, empty_specs) == ""
    assert kodate._parseSaikenchiku(soup, empty_specs) == ""

    tochi = SumifuTochiParser()
    assert tochi._parseCurrentStatus(soup, empty_specs) == ""
    assert tochi._parseKouzou(soup, empty_specs) == ""
    assert tochi._parseChikunengetsuStr(soup, empty_specs) == ""
    assert tochi._parseTochikenri(soup, empty_specs) == ""
    assert tochi._parseTochiMensekiStr(soup, empty_specs) == ""
    assert tochi._parseKenchikuJoken(soup, empty_specs) == ""
    assert tochi._parseSetsudou(soup, empty_specs) == ""
    assert tochi._parseYoutoChiiki(soup, empty_specs) == ""
    assert tochi._parseKokudoHou(soup, empty_specs) == ""
    assert tochi._parseChisei(soup, empty_specs) == ""
    assert tochi._parseChimoku(soup, empty_specs) == ""
    assert tochi._parseChimokuChisei(soup, empty_specs) == ""

    invest = SumifuInvestmentApartmentParser()
    assert invest._parseChikunengetsuStr(soup, empty_specs) == ""
    assert invest._parseTochikenri(soup, empty_specs) == ""


def test_tokyu_no_dummy_fallbacks():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    empty_specs = {}

    kodate = TokyuKodateParser()
    assert kodate._parseKenchikuJoken(soup, empty_specs) == ""

    tochi = TokyuTochiParser()
    assert tochi._parseDouroKubun(soup, empty_specs) == ""
    assert tochi._parseChisei(soup, empty_specs) == ""
    assert tochi._parseBoukaChiiki(soup, empty_specs) == ""
    assert tochi._parseSonotaChiiki(soup, empty_specs) == ""
    assert tochi._parseKenchikuJoken(soup, empty_specs) == ""
    assert tochi._parseSaikenchiku(soup, empty_specs) == ""
    assert tochi._parseKokudoHou(soup, empty_specs) == ""
