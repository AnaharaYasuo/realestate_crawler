import pytest
from unittest.mock import MagicMock, patch

from package.models.tokyu import TokyuKodate, TokyuMansion
from package.models.evaluation import PropertyEvaluation
from scripts.maintenance.cleanse_issue_1097_data import cleanse_tokyu_anomalies, find_anomaly_urls


@pytest.mark.django_db
def test_cleanse_tokyu_anomalies():
    # Setup test properties
    url_bad_kodate = "https://www.livable.co.jp/kodate/TEST001/"
    url_good_kodate = "https://www.livable.co.jp/kodate/TEST002/"

    TokyuKodate.objects.create(
        pageUrl=url_bad_kodate,
        propertyName="テスト物件1",
        priceStr="5000万円",
        price=50000000,
        address="東京都渋谷区",
        madori="{'value': '3LDK', 'element': None}",
        tochiMenseki=100.0,
        tatemonoMenseki=80.0,
        chikunengetsuStr="2020年1月",
        kouzou="木造",
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
        needs_recrawl=False,
    )

    TokyuKodate.objects.create(
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

    # Test find_anomaly_urls
    anomalies = find_anomaly_urls()
    assert url_bad_kodate in anomalies
    assert url_good_kodate not in anomalies

    # Test dry run
    dry_count = cleanse_tokyu_anomalies(dry_run=True)
    assert dry_count == 1
    eval_bad = PropertyEvaluation.objects.get(property_url=url_bad_kodate)
    assert eval_bad.needs_recrawl is False

    # Test actual run
    actual_count = cleanse_tokyu_anomalies(dry_run=False)
    assert actual_count == 1
    eval_bad.refresh_from_db()
    assert eval_bad.needs_recrawl is True
    assert eval_bad.data_quality_issue == "tokyu_madori_dict_bug"

    eval_good = PropertyEvaluation.objects.get(property_url=url_good_kodate)
    assert eval_good.needs_recrawl is False
