import pytest
from unittest.mock import MagicMock, patch

from package.models.tokyu import TokyuKodate, TokyuMansion
from package.models.evaluation import PropertyEvaluation
from scripts.maintenance.cleanse_issue_1097_data import (
    extract_value_from_dict_repr,
    cleanse_tokyu_in_place,
)


def test_extract_value_from_dict_repr():
    # Single quotes
    assert extract_value_from_dict_repr("{'value': '3LDK', 'element': None}") == "3LDK"
    # Double quotes
    assert extract_value_from_dict_repr('{"value": "2SLDK", "element": null}') == "2SLDK"
    # Complex strings
    assert extract_value_from_dict_repr("{'value': '4LDK＋S（納戸）', 'row': 'test'}") == "4LDK＋S（納戸）"
    # Plain string should be untouched
    assert extract_value_from_dict_repr("3LDK") == "3LDK"
    assert extract_value_from_dict_repr(None) is None
    assert extract_value_from_dict_repr("") == ""


@pytest.mark.django_db
def test_cleanse_tokyu_in_place():
    # Setup test properties
    url_bad_kodate = "https://www.livable.co.jp/kodate/TEST001/"
    url_good_kodate = "https://www.livable.co.jp/kodate/TEST002/"

    bad_kodate = TokyuKodate.objects.create(
        pageUrl=url_bad_kodate,
        propertyName="テスト物件1",
        priceStr="5000万円",
        price=50000000,
        address="東京都渋谷区",
        madori="{'value': '3LDK', 'element': None}",
        tochiMenseki=100.0,
        tatemonoMenseki=80.0,
        chikunengetsuStr="2020年1月",
        kouzou="{'value': '木造2階建', 'element': None}",
        setsumen="4m",
        douroHaba="4m",
        youtoChiiki="第一種住居地域",
        setsudou="公道",
    )
    PropertyEvaluation.objects.create(
        company="tokyu",
        property_type="kodate",
        property_url=url_bad_kodate,
        property_id=1,
        needs_recrawl=True,
        data_quality_issue="tokyu_madori_dict_bug",
    )

    good_kodate = TokyuKodate.objects.create(
        pageUrl=url_good_kodate,
        propertyName="テスト物件2",
        priceStr="6000万円",
        price=60000000,
        address="東京都港区",
        madori="4LDK",
        tochiMenseki=120.0,
        tatemonoMenseki=90.0,
        chikunengetsuStr="2021年1月",
        kouzou="木造",
        setsumen="5m",
        douroHaba="5m",
        youtoChiiki="第一種低層住居専用地域",
        setsudou="公道",
    )
    PropertyEvaluation.objects.create(
        company="tokyu",
        property_type="kodate",
        property_url=url_good_kodate,
        property_id=2,
        needs_recrawl=False,
    )

    # Test dry run
    stats_dry = cleanse_tokyu_in_place(dry_run=True)
    assert stats_dry["TokyuKodate"] == 1
    assert stats_dry["PropertyEvaluation_reset"] == 1

    bad_kodate.refresh_from_db()
    assert bad_kodate.madori == "{'value': '3LDK', 'element': None}"
    assert bad_kodate.kouzou == "{'value': '木造2階建', 'element': None}"
    eval_bad = PropertyEvaluation.objects.get(property_url=url_bad_kodate)
    assert eval_bad.needs_recrawl is True
    assert eval_bad.data_quality_issue == "tokyu_madori_dict_bug"

    # Test actual run
    stats_actual = cleanse_tokyu_in_place(dry_run=False)
    assert stats_actual["TokyuKodate"] == 1
    assert stats_actual["PropertyEvaluation_reset"] == 1

    bad_kodate.refresh_from_db()
    assert bad_kodate.madori == "3LDK"
    assert bad_kodate.kouzou == "木造2階建"

    eval_bad.refresh_from_db()
    assert eval_bad.needs_recrawl is False
    assert eval_bad.data_quality_issue == ""

    eval_good = PropertyEvaluation.objects.get(property_url=url_good_kodate)
    assert eval_good.needs_recrawl is False
    assert eval_good.data_quality_issue == ""
