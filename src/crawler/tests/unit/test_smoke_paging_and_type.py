"""Unit tests for paging + property-type helpers in crawl smoke engine."""
from __future__ import annotations

from package.utils.crawl_smoke_engine import (
    _soft_residential_type_ok,
    evaluate_paging_result,
    expected_detector_type,
    property_types_compatible,
)


class _Item:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_soft_residential_type_ok_mansion_with_senyu():
    item = _Item(senyuMenseki=42.5)
    assert _soft_residential_type_ok("kodate", "mansion", item, None, "seibu")
    assert _soft_residential_type_ok("tochi", "mansion", item, None, "keisei")


def test_soft_residential_type_ok_sumai1_kodate_tochi():
    item = _Item()
    assert _soft_residential_type_ok("tochi", "kodate", item, None, "sumai1")
    assert not _soft_residential_type_ok("tochi", "kodate", item, None, "mitsui")


def test_assert_property_type_trusts_url_path_over_html_noise():
    """Sekisui shared nav can false-trigger apartment; URL path wins."""
    from bs4 import BeautifulSoup
    from package.utils.crawl_smoke_engine import assert_property_type_for_smoke

    class _Parser:
        property_type = "kodate"
        company = "sekisui"

    item = _Item(propertyName="テスト戸建")
    page = BeautifulSoup(
        "<html><title>戸建</title><body>投資 利回り アパート募集</body></html>",
        "html.parser",
    )
    assert_property_type_for_smoke(
        _Parser(),
        item,
        "https://sumusite.sekisuihouse.co.jp/kanto/kodate/detail/C20010064110/",
        page,
        "kodate",
        company="sekisui",
    )


class _Parser:
    def __init__(self, property_type: str):
        self.property_type = property_type


def test_expected_detector_type_maps_job_and_parser():
    assert expected_detector_type("mansion", _Parser("mansion")) == "mansion"
    assert expected_detector_type("kodate", _Parser("kodate")) == "kodate"
    assert expected_detector_type("tochi", _Parser("tochi")) == "tochi"
    assert expected_detector_type("invest_apartment", _Parser("investmentapartment")) == "apartment"
    assert expected_detector_type("investment", _Parser("investment")) == "apartment"
    # Homes "mansion" job uses investment-apartment parser on toushi.homes
    assert expected_detector_type("mansion", _Parser("investmentapartment")) == "apartment"
    assert expected_detector_type("kodate", _Parser("kodate"), company="homes") == "apartment"
    assert expected_detector_type("tochi", _Parser("tochi"), company="homes") == "apartment"


def test_property_types_compatible():
    assert property_types_compatible("mansion", "mansion")
    assert property_types_compatible("apartment", "investment")
    assert property_types_compatible("apartment", "invest_apartment")
    assert not property_types_compatible("tochi", "mansion")
    assert not property_types_compatible("kodate", "mansion")
    assert property_types_compatible("mansion", "apartment")
    assert property_types_compatible("apartment", "mansion")
    # tokyo816 has no condominiums; 建売 (kodate) is the mansion-job candidate.
    assert property_types_compatible("kodate", "mansion", company="heim")
    assert property_types_compatible("mansion", "kodate", company="heim")
    assert property_types_compatible("tochi", "kodate", company="sumai1")
    assert not property_types_compatible("tochi", "kodate")


def test_evaluate_paging_advanced():
    pages, exhausted, ok = evaluate_paging_result(
        list_url="https://example.com/list/?page=1",
        next_url="https://example.com/list/?page=2",
        next_fetch_ok=True,
    )
    assert pages == 2
    assert exhausted is False
    assert ok is True


def test_evaluate_paging_exhausted_when_no_next():
    pages, exhausted, ok = evaluate_paging_result(
        list_url="https://example.com/list/",
        next_url="",
        next_fetch_ok=False,
    )
    assert pages == 1
    assert exhausted is True
    assert ok is True


def test_evaluate_paging_fails_on_same_url_loop():
    pages, exhausted, ok = evaluate_paging_result(
        list_url="https://example.com/list/",
        next_url="https://example.com/list/",
        next_fetch_ok=True,
    )
    assert pages == 1
    assert exhausted is False
    assert ok is False


def test_evaluate_paging_fails_when_next_fetch_fails():
    pages, _exhausted, ok = evaluate_paging_result(
        list_url="https://example.com/list/1",
        next_url="https://example.com/list/2",
        next_fetch_ok=False,
    )
    assert pages == 1
    assert ok is False
