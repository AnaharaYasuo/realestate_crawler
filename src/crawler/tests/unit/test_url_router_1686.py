"""Unit tests for Issue #1686 UrlRouter pattern fixes."""

from package.utils.url_router import UrlRouter


def test_toho_house_sch_detail_resolves_to_toho():
    route = UrlRouter.resolve("https://www.toho-house.co.jp/sch/detail.php?k_number=83999&div=001")
    assert route is not None
    assert route["site"] == "toho"


def test_rehouse_s_kodate_resolves_to_mitsui_kodate():
    route = UrlRouter.resolve("https://www.rehouse.co.jp/buy/s_kodate/bkdetail/F08BTA2F/")
    assert route is not None
    assert route["site"] == "mitsui"
    assert route["parser_cls"] == "MitsuiKodateParser"
