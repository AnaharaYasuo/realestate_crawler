"""Unit and regression tests for Issue #1160:
- Watchdog progress file matching, cross-job touch isolation, and fire-and-forget timeout cleanup
- Bulk ML evaluation DB OperationalError (2013/9001) retry and deduplication batch prefetch
- Detail page single-save lifecycle and concrete model full_clean() validation
- Parser regressions (rearie top-page redirect, tokyu_mansion investment skip, tokyu_kodate Decimal fields,
  homes_investment_apartment grossYield overflow, sumai1_investment residential URL skip, toho h1 prefix strip)
"""
import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from django.db import OperationalError
import pytest

import setup_env  # noqa: F401
from package.api import api as api_module
from package.api.differential import (
    _detect_company_and_type_from_model,
    _touch_differential_progress,
)
from package.ml.evaluation.targets import _iter_target_items
from package.models.evaluation import PropertyEvaluation
from package.models.homes import HomesInvestmentApartment
from package.models.mitsui import MitsuiInvestmentKodate
from package.models.sumifu import SumifuMansion
from package.models.tokyu import TokyuInvestmentApartment, TokyuKodate, TokyuMansion
from package.parser.baseParser import ListingEndedException, SkipPropertyException
from package.parser.homesParser import HomesInvestmentApartmentParser
from package.parser.rearieParser import RearieMansionParser
from package.parser.sumai1Parser import Sumai1InvestmentParser
from package.parser.tohoParser import TohoTochiParser
from package.parser.tokyuParser import TokyuKodateParser, TokyuMansionParser
from package.utils.deduplication import (
    _get_real_property,
    _prefetch_real_properties,
    clear_real_property_cache,
)
from scripts.maintenance.validate_data import _fetch_model_candidates_with_retry


class TestWatchdogAndFireAndForgetHardening:
    def test_detect_company_and_type_from_model_investment_subtypes(self):
        """_detect_company_and_type_from_model maps InvestmentApartment/Kodate to invest_apartment/invest_kodate."""
        assert _detect_company_and_type_from_model(TokyuInvestmentApartment) == ("tokyu", "invest_apartment")
        assert _detect_company_and_type_from_model(MitsuiInvestmentKodate) == ("mitsui", "invest_kodate")
        assert _detect_company_and_type_from_model(TokyuMansion) == ("tokyu", "mansion")

    def test_touch_progress_respects_crawler_job_env_vars(self, monkeypatch):
        """When CRAWLER_JOB_COMPANY and CRAWLER_JOB_TYPE are set, all touch helpers touch only that exact job."""
        monkeypatch.setenv("CRAWLER_JOB_COMPANY", "mitsui")
        monkeypatch.setenv("CRAWLER_JOB_TYPE", "mansion")

        with patch("package.api.differential.touch_crawler_progress") as mock_diff_touch:
            _touch_differential_progress(MitsuiInvestmentKodate)
            mock_diff_touch.assert_called_once_with("mitsui", "mansion")

        with patch("package.api.api.touch_crawler_progress") as mock_api_touch:
            api_module._touch_active_progress_files()
            mock_api_touch.assert_called_once_with("mitsui", "mansion")

    def test_api_touch_watchdog_progress_normalizes_investment_subtypes(self, monkeypatch):
        """When CRAWLER_JOB_* env vars are unset, _touch_watchdog_progress normalizes InvestmentApartment -> invest_apartment."""
        monkeypatch.delenv("CRAWLER_JOB_COMPANY", raising=False)
        monkeypatch.delenv("CRAWLER_JOB_TYPE", raising=False)

        dummy_proc = MagicMock()
        dummy_proc._detect_company_name.return_value = "tokyu"

        with (
            patch("package.api.api.PropertyTypeDetector.detect_from_object", return_value="InvestmentApartment"),
            patch("package.api.api.touch_crawler_progress") as mock_touch,
        ):
            api_module.ApiAsyncProcBase._touch_watchdog_progress(dummy_proc, item=TokyuInvestmentApartment())
            mock_touch.assert_called_once_with("tokyu", "invest_apartment")

    def test_cancel_unstarted_futures_shuts_down_executor_on_timeout(self, tmp_path, monkeypatch):
        """On fire-and-forget wait timeout, _cancel_unstarted_futures_on_stop shuts down _local_worker_executor non-blockingly."""
        stop_file = tmp_path / "stop.flag"
        monkeypatch.setattr(api_module, "STOP_FLAG_FILE", str(stop_file))
        mock_executor = MagicMock()
        monkeypatch.setattr(api_module, "_local_worker_executor", mock_executor)

        api_module._cancel_unstarted_futures_on_stop(timeout_expired=True)

        assert stop_file.exists()
        mock_executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        assert api_module._local_worker_executor is None


class TestBulkMlAndDeduplicationResilience:
    def test_iter_target_items_retries_on_operational_error(self):
        """_iter_target_items closes old connections and retries when OperationalError (2013/9001) occurs."""
        mock_item = MagicMock()
        mock_item.id = 10
        mock_item.pk = 10
        mock_item.pageUrl = "https://example.com/p/10"

        call_count = {"n": 0}

        def fake_fetch_chunk(model, last_pk, batch_size):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OperationalError(2013, "Lost connection to server during query")
            if last_pk == 0:
                return [mock_item]
            return []

        with (
            patch.object(TokyuMansion.objects, "filter") as mock_filter,
            patch("package.ml.evaluation.targets.close_old_connections") as mock_close,
            patch("package.ml.evaluation.targets.time.sleep"),
        ):
            def filter_side_effect(**kwargs):
                qs = MagicMock()
                last_pk = kwargs.get("pk__gt", kwargs.get("id__gt", 0))
                qs.order_by.return_value.__getitem__.side_effect = lambda s: fake_fetch_chunk(TokyuMansion, last_pk, s)
                return qs

            mock_filter.side_effect = filter_side_effect
            items = [it for it, _ in _iter_target_items(TokyuMansion, {}, force=True) if it is not None]

        assert len(items) == 1
        assert items[0].id == 10
        assert mock_close.called

    def test_prefetch_real_properties_and_retry_on_operational_error(self):
        """_prefetch_real_properties batches IDs per model and retries on OperationalError."""
        clear_real_property_cache()
        eval_rec = PropertyEvaluation(
            company="tokyu",
            property_type="mansion",
            property_id=42,
            property_url="https://www.livable.co.jp/mansion/C42/",
        )
        fake_prop = TokyuMansion(id=42, propertyName="テストマンション")
        attempts = {"n": 0}

        def filter_side_effect(**kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise OperationalError(2006, "MySQL server has gone away")
            return [fake_prop]

        with (
            patch.object(TokyuMansion.objects, "filter", side_effect=filter_side_effect),
            patch("package.utils.deduplication.close_old_connections") as mock_close,
        ):
            _prefetch_real_properties([eval_rec])
            resolved = _get_real_property(eval_rec)

        assert resolved is fake_prop
        assert mock_close.called
        clear_real_property_cache()

    def test_validate_data_fetch_model_candidates_retries_on_operational_error(self):
        """_fetch_model_candidates_with_retry retries when OperationalError occurs during model scan."""
        fake_item = MagicMock()
        calls = {"n": 0}

        def all_side_effect():
            calls["n"] += 1
            if calls["n"] == 1:
                raise OperationalError(2013, "Lost connection")
            return [fake_item]

        mock_model = MagicMock()
        mock_model.__name__ = "TokyuMansion"
        mock_model.objects.all.side_effect = all_side_effect

        with (
            patch("scripts.maintenance.validate_data.close_old_connections") as mock_close,
            patch("scripts.maintenance.validate_data.time.sleep"),
        ):
            res = _fetch_model_candidates_with_retry(mock_model, None)

        assert res == [fake_item]
        assert mock_close.call_count >= 2


class TestParserAndModelRegressions1160:
    def test_rearie_top_page_redirect_raises_listing_ended(self):
        """Rearie detail page redirected to Panasonic Homes top page raises ListingEndedException."""
        html = "<html><head><title>- パナソニック ホームズ株式会社 - Panasonic</title></head><body><h1></h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = RearieMansionParser("")
        with pytest.raises(ListingEndedException):
            parser._parsePropertyDetailPage(TokyuMansion(), soup)

    def test_tokyu_mansion_skips_fudosan_toushi_url_and_title(self):
        """TokyuMansionParser skips /fudosan-toushi/ investment URLs and '｜投資用物件' titles."""
        parser = TokyuMansionParser("")
        with pytest.raises(SkipPropertyException):
            parser._reject_non_property_url("https://www.livable.co.jp/fudosan-toushi/C11268A17/")

        html = "<html><head><title>さいたま市｜投資用物件（一棟マンション）｜東急リバブル</title></head><body><h1>物件名</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(SkipPropertyException):
            parser._parsePropertyDetailPage(TokyuMansion(), soup)

    def test_tokyu_kodate_decimal_fields_and_douro_haba_fallback(self):
        """TokyuKodateParser assigns Decimal|None (never '') to setsumen/douroHaba and falls back to 道路幅員."""
        html = """
        <html><head><title>東山田町 新築一戸建て｜東急リバブル</title></head>
        <body>
          <h1>新築分譲住宅 東山田町</h1>
          <dl><dt>価格</dt><dd>5,480万円</dd></dl>
          <dl><dt>所在地</dt><dd>神奈川県横浜市都筑区東山田町</dd></dl>
          <dl><dt>交通</dt><dd>グリーンライン「東山田」駅 徒歩13分</dd></dl>
          <dl><dt>建物面積</dt><dd>96.47m2</dd></dl>
          <dl><dt>土地面積</dt><dd>125.06m2</dd></dl>
          <dl><dt>間取り</dt><dd>4LDK</dd></dl>
          <dl><dt>完成時期(築年月)</dt><dd>2026年8月</dd></dl>
          <dl><dt>道路幅員</dt><dd>6.0m</dd></dl>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        parser = TokyuKodateParser("")
        item = parser._parsePropertyDetailPage(TokyuKodate(), soup)
        assert item.setsumen is None
        assert item.douroHaba == Decimal("6.0")
        item.pageUrl = "https://www.livable.co.jp/kodate/C1234567/"
        item.full_clean(validate_unique=False)

    def test_homes_investment_apartment_clamps_anomalous_gross_yield(self):
        """Anomalous grossYield >= 1000 (e.g. 67624.00%) is sanitized to None so DecimalField(5,2) does not fail."""
        html = """
        <html><head><title>一棟ビル｜LIFULL HOME'S</title></head>
        <body>
          <h1><span class="bukkenName">テスト一棟マンション</span></h1>
          <table>
            <tr><th>物件名</th><td>テスト一棟マンション</td></tr>
            <tr><th>価格</th><td>6,480万円</td></tr>
            <tr><th>利回り</th><td><span class="prg-rimawariTableItem">67624.00％</span></td></tr>
            <tr><th>満室想定年収</th><td><td class="prg-annualIncomeTableItem">420万円</td></td></tr>
            <tr><th>所在地</th><td>東京都新宿区西新宿1丁目</td></tr>
            <tr><th>交通</th><td>JR山手線 新宿駅 徒歩5分</td></tr>
            <tr><th>建物面積</th><td>210.50m2</td></tr>
            <tr><th>土地面積</th><td>150.00m2</td></tr>
            <tr><th>築年月</th><td>2010年5月</td></tr>
          </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        parser = HomesInvestmentApartmentParser("")
        item = parser._parsePropertyDetailPage(HomesInvestmentApartment(), soup)
        assert item.grossYield is None
        assert item.annualRent == 4200000
        item.pageUrl = "https://toushi.homes.co.jp/bukkendetail/index/4794546/"
        item.full_clean(validate_unique=False)

    def test_sumai1_investment_rejects_residential_buyers_urls(self):
        """Sumai1InvestmentParser rejects /buyers/tochi/, /buyers/kodate/, and /buyers/mansion/ URLs."""
        parser = Sumai1InvestmentParser("")
        for res_url in [
            "https://www.sumai1.com/buyers/tochi/bukken/buk_She260082/",
            "https://www.sumai1.com/buyers/kodate/bukken/buk_YAAA14936/",
            "https://www.sumai1.com/buyers/mansion/bukken/buk_NF85C6023/",
        ]:
            with pytest.raises(SkipPropertyException):
                parser._reject_non_property_url(res_url)

    def test_toho_strips_favorite_button_prefix_from_h1(self):
        """TohoBaseParser strips 'お気に入りに追加' prefix from h1 propertyName."""
        html = "<html><body><h1><span>お気に入りに追加</span>横浜市鶴見区東寺尾6丁目 売地</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        parser = TohoTochiParser()
        assert parser._parsePropertyName(soup) == "横浜市鶴見区東寺尾6丁目 売地"

    def test_sumifu_mansion_allows_blank_syuzen_tsumitate_str(self):
        """SumifuMansion full_clean() succeeds when syuzenTsumitateStr or tochikenri is empty string."""
        item = SumifuMansion(
            propertyName="シティタワー武蔵小杉",
            pageUrl="https://www.stepon.co.jp/mansion/detail_36253292/",
            price=89800000,
            priceStr="8,980万円",
            address="神奈川県川崎市中原区新丸子東3丁目",
            traffic="東急東横線「武蔵小杉」駅 徒歩4分",
            senyuMenseki=Decimal("70.12"),
            senyuMensekiStr="70.12㎡",
            madori="3LDK",
            kaisu=20,
            kaisuStr="20階",
            chikunengetsu=datetime.date(2016, 1, 1),
            chikunengetsuStr="2016年1月",
            kanrihiStr="",
            syuzenTsumitateStr="",
            tochikenri="",
        )
        item.full_clean(validate_unique=False)
