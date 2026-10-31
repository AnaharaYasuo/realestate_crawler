import asyncio
import os
import threading
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from package.parser.athomeParser import AthomeKodateParser, AthomeMansionParser
from package.parser.baseParser import ServerBusyException, SkipPropertyException
from package.parser.homesParser import HomesMansionParser, HomesTochiParser
from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser
from package.parser.mitsuiParser import (
    MitsuiKodateParser,
    MitsuiMansionParser,
    MitsuiTochiParser,
)
from package.parser.sumifuParser import (
    SumifuInvestmentApartmentParser,
    SumifuMansionParser,
)
from package.parser.tokyuParser import (
    TokyuInvestmentApartmentParser,
    TokyuMansionParser,
)
from package.utils.crawler_diagnostics import (
    cleanup_job_diagnostic_dir,
    clear_thread_activity,
    collect_job_thread_activities,
    format_hang_diagnostic_summary,
    record_thread_activity,
    save_hang_diagnostic_snapshot,
    set_diagnostic_job_context,
)
from package.utils.crawler_watchdog import get_progress_file_path, touch_crawler_progress
from package.utils.data_validator import PropertyDataValidator
from package.utils.logging_config import configure_job_file_logging
from package.utils.newrelic_helper import (
    collect_hardware_resource_metrics,
    record_container_sample,
    record_hang_diagnostic_event,
)
from package.utils.property_type_detector import PropertyTypeDetector


class TestObservabilityAndPerThreadDiagnostics:
    def test_touch_crawler_progress_remains_zero_byte_liveness_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CRAWLER_PROGRESS_DIR", str(tmp_path))
        touch_crawler_progress("mitsui", "mansion")
        p = get_progress_file_path("mitsui", "mansion")
        assert p.exists()
        assert p.stat().st_size == 0

    def test_per_thread_lock_free_diagnostic_files_do_not_share_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "package.utils.crawler_diagnostics._get_job_diag_dir",
            lambda company="", property_type="": tmp_path / f"{company or 'tokyu'}_{property_type or 'mansion'}",
        )
        set_diagnostic_job_context("tokyu", "mansion")

        barrier = threading.Barrier(2)
        results = {}

        def worker(idx: int, url: str):
            set_diagnostic_job_context("tokyu", "mansion")
            record_thread_activity(
                "detail_fetch",
                current_url=url,
                parent_list_url="https://www.livable.co.jp/kounyu/mansion/list/",
                extra={"worker_idx": idx},
                force_flush=True,
            )
            barrier.wait(timeout=5)
            results[idx] = threading.get_ident()

        t1 = threading.Thread(target=worker, args=(1, "https://www.livable.co.jp/mansion/C111/"))
        t2 = threading.Thread(target=worker, args=(2, "https://www.livable.co.jp/mansion/C222/"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        diag_dir = tmp_path / "tokyu_mansion"
        files = sorted(p.name for p in diag_dir.glob("thread_*.json"))
        assert f"thread_{results[1]}.json" in files
        assert f"thread_{results[2]}.json" in files
        assert results[1] != results[2]

        activities = collect_job_thread_activities("tokyu", "mansion")
        urls = {a.get("current_url") for a in activities}
        assert "https://www.livable.co.jp/mansion/C111/" in urls
        assert "https://www.livable.co.jp/mansion/C222/" in urls

        snap = save_hang_diagnostic_snapshot(
            "tokyu",
            "mansion",
            reason="unit_test_hang",
            include_current_process_stacks=True,
        )
        assert snap["primary_target_url"] in urls
        assert snap["primary_parent_list_url"] == "https://www.livable.co.jp/kounyu/mansion/list/"
        assert "hardware_and_network" in snap
        assert "database" in snap
        summary = format_hang_diagnostic_summary(snap)
        assert "Primary URL:" in summary
        assert "Resources:" in summary
        assert "Network:" in summary
        assert "Database:" in summary

        clear_thread_activity()
        cleanup_job_diagnostic_dir("tokyu", "mansion")

    def test_hardware_resource_metrics_and_newrelic_sample(self, monkeypatch):
        monkeypatch.setenv("NEW_RELIC_LICENSE_KEY", "dummy-key")
        metrics = collect_hardware_resource_metrics()
        assert "memoryUsageMb" in metrics
        assert "cpuPercent" in metrics
        assert "netBytesRecv" in metrics
        assert "netBytesSent" in metrics
        assert "tcpEstablishedCount" in metrics
        assert "dbConnectionsOpen" in metrics
        assert "activeThreadsCount" in metrics

        mock_agent = MagicMock()
        with patch("package.utils.newrelic_helper._get_agent", return_value=mock_agent), patch(
            "package.utils.newrelic_helper._get_application", return_value=MagicMock()
        ):
            ok = record_container_sample(
                service_name="crawler-mitsui-mansion",
                custom_metrics={"company": "mitsui", "propertyType": "mansion"},
            )
            assert ok is True
            assert mock_agent.record_custom_event.called

            ok_hang = record_hang_diagnostic_event(
                {
                    "company": "mitsui",
                    "property_type": "mansion",
                    "pid": 12345,
                    "reason": "HangSilentFailure",
                    "primary_target_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/F1/",
                    "primary_parent_list_url": "https://www.rehouse.co.jp/buy/mansion/",
                    "active_phases": ["detail_fetch"],
                    "hardware_and_network": metrics,
                    "database": {"connections_open": 1, "proxysql_reachable": True, "proxysql_ping_ms": 1.2},
                }
            )
            assert ok_hang is True
            assert mock_agent.record_custom_event.call_count >= 2

    def test_configure_job_file_logging_writes_job_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        log_path = configure_job_file_logging("mitsui", "mansion", "20261031")
        assert log_path is not None
        assert os.path.exists(log_path)


class TestDataIntegrityAndContaminationFixes:
    def test_mitsui_td_table_header_specs_and_traffic_extraction(self):
        html = """
        <html><body>
          <h1>テスト三井マンション</h1>
          <table>
            <tr><td class="table-header label">価格</td><td class="table-data">5,480万円</td></tr>
            <tr><td class="table-header label">専有面積</td><td class="table-data">72.45㎡</td></tr>
            <tr><td class="table-header label">間取り</td><td class="table-data">3LDK</td></tr>
            <tr><td class="table-header label">所在階</td><td class="table-data">5階 / 地上10階建</td></tr>
            <tr><td class="table-header label">築年月</td><td class="table-data">2015年3月</td></tr>
            <tr><td class="table-header label">所在地</td><td class="table-data">東京都港区白金１丁目</td></tr>
            <tr><td class="table-header label">交通</td><td class="table-data"><p>東京メトロ南北線 白金高輪 徒歩6分</p></td></tr>
          </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        parser = MitsuiMansionParser()
        item = parser.createEntity()
        item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FTEST01/"
        parsed = parser._parsePropertyDetailPage(item, soup)
        assert parsed.price == 54800000
        assert float(parsed.senyuMenseki) == pytest.approx(72.45)
        assert "白金高輪" in parsed.traffic
        assert parsed.station1 == "白金高輪"
        assert parsed.railway1 == "東京メトロ南北線"
        is_valid, reasons = PropertyDataValidator.validate_property(parsed, "mansion")
        assert is_valid, f"Unexpected validation errors: {reasons}"

    def test_mitsui_undetermined_price_skips(self):
        html = """
        <html><body>
          <h1>パークシティ中野 ザ タワー エアーズ</h1>
          <table>
            <tr><td class="table-header label">価格</td><td class="table-data">価格未定</td></tr>
            <tr><td class="table-header label">専有面積</td><td class="table-data">未定</td></tr>
          </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        parser = MitsuiMansionParser()
        item = parser.createEntity()
        item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/"
        with pytest.raises(SkipPropertyException):
            parser._parsePropertyDetailPage(item, soup)

    def test_mitsui_cross_type_url_guards(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        for parser_cls, bad_url in [
            (MitsuiTochiParser, "https://www.rehouse.co.jp/buy/mansion/bkdetail/F1/"),
            (MitsuiMansionParser, "https://www.rehouse.co.jp/buy/tochi/bkdetail/F2/"),
            (MitsuiKodateParser, "https://www.rehouse.co.jp/buy/mansion/bkdetail/F3/"),
        ]:
            parser = parser_cls()
            item = parser.createEntity()
            item.pageUrl = bad_url
            with pytest.raises(SkipPropertyException):
                parser._parsePropertyDetailPage(item, soup)

    def test_property_type_detector_ignores_kodate_simile_on_mansion(self):
        detected = PropertyTypeDetector.detect(
            url="https://www.athome.co.jp/mansion/1155089427/",
            title="～戸建のような庭付の邸宅～ロータリーライフ与野 1階 ２ＳＤＫ",
            specs={"物件種目": "中古マンション", "専有面積": "55.0㎡", "階建 / 階": "5階建 / 1階"},
        )
        assert detected == "mansion"

    def test_athome_kodate_rejects_mansion_url_and_mansion_extracts_floor_from_title(self):
        soup_k = BeautifulSoup("<html><body><h1>テスト</h1></body></html>", "html.parser")
        k_parser = AthomeKodateParser()
        k_item = k_parser.createEntity()
        k_item.pageUrl = "https://www.athome.co.jp/mansion/1155089427/"
        with pytest.raises(SkipPropertyException):
            k_parser._parsePropertyDetailPage(k_item, soup_k)

        html_m = """
        <html><head><title>ライオンズマンション 3階 2LDK</title></head><body>
          <h1>ライオンズマンション 3階</h1>
          <table>
            <tr><th>価格</th><td>3,280万円</td></tr>
            <tr><th>所在地</th><td>東京都新宿区西新宿１丁目</td></tr>
            <tr><th>交通</th><td>ＪＲ山手線 新宿駅 徒歩8分</td></tr>
            <tr><th>専有面積</th><td>55.20m²</td></tr>
            <tr><th>間取り</th><td>2LDK</td></tr>
            <tr><th>築年月</th><td>2010年5月</td></tr>
            <tr><th>階建 / 階</th><td>地上10階建</td></tr>
          </table>
        </body></html>
        """
        m_parser = AthomeMansionParser()
        m_item = m_parser.createEntity()
        m_item.pageUrl = "https://www.athome.co.jp/mansion/chuko/tokyo/shinjuku-city/12345678/"
        parsed_m = m_parser._parsePropertyDetailPage(m_item, BeautifulSoup(html_m, "html.parser"))
        assert "3階" in parsed_m.kaisuStr
        assert PropertyDataValidator._has_located_floor(parsed_m.kaisuStr)

    def test_sumifu_and_tokyu_url_guards(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        s_inv = SumifuInvestmentApartmentParser()
        s_item = s_inv.createEntity()
        s_item.pageUrl = "https://www.stepon.co.jp/tochi/detail_12345/"
        with pytest.raises(SkipPropertyException):
            s_inv._parsePropertyDetailPage(s_item, soup)

        s_man = SumifuMansionParser()
        sm_item = s_man.createEntity()
        sm_item.pageUrl = "https://www.stepon.co.jp/kodate/detail_12345/"
        with pytest.raises(SkipPropertyException):
            s_man._parsePropertyDetailPage(sm_item, soup)

        t_inv = TokyuInvestmentApartmentParser()
        ti_item = t_inv.createEntity()
        ti_item.pageUrl = "https://www.livable.co.jp/tochi/C12345/"
        with pytest.raises(SkipPropertyException):
            t_inv._parsePropertyDetailPage(ti_item, soup)

        t_man = TokyuMansionParser()
        with pytest.raises(SkipPropertyException):
            t_man._reject_non_property_url("https://www.livable.co.jp/kodate/C12345/")

    def test_homes_root_page_excludes_chuko_index_link_and_tochi_skips_zero_area(self):
        html = """
        <html><body>
          <a href="/mansion/chuko/">中古マンショントップ</a>
          <a href="https://www.homes.co.jp/mansion/b-123456/">物件詳細</a>
        </body></html>
        """
        parser = HomesMansionParser()

        async def _collect():
            return [it.url async for it in parser.parseRootPage(BeautifulSoup(html, "html.parser"))]

        urls = asyncio.run(_collect())
        assert "https://www.homes.co.jp/mansion/b-123456/" in urls
        assert "https://www.homes.co.jp/mansion/chuko/" not in urls

        tochi_parser = HomesTochiParser()
        t_item = tochi_parser.createEntity()
        t_item.pageUrl = "https://www.homes.co.jp/tochi/b-999999/"
        with pytest.raises(SkipPropertyException):
            tochi_parser._parsePropertyDetailPage(
                t_item,
                BeautifulSoup("<html><body><table><tr><th>価格</th><td>1000万円</td></tr></table></body></html>", "html.parser"),
            )

    def test_kenbiya_waf_fast_fail_raises_server_busy(self):
        parser = KenbiyaInvestmentApartmentParser()
        empty_soup = BeautifulSoup("<html><body><div>Access Denied</div></body></html>", "html.parser")

        async def _collect():
            return [it async for it in parser.parseRootPage(empty_soup)]

        with pytest.raises(ServerBusyException):
            asyncio.run(_collect())

    def test_validator_allows_low_price_rural_tochi_and_apartment_type(self):
        tochi_obj = MagicMock(
            propertyName="比企郡吉見町 大字北吉見 住宅用地",
            address="埼玉県比企郡吉見町大字北吉見",
            traffic="東武東上線 東松山駅 バス15分",
            station1="東松山",
            price=300000,
            tochiMenseki=120.0,
            chimoku="宅地",
            biko="",
            pageUrl="https://www.athome.co.jp/tochi/1044314084/",
        )
        valid, reasons = PropertyDataValidator.validate_property(tochi_obj, "tochi")
        assert valid, f"Rural tochi >= 10万円 should be valid, got: {reasons}"

        apt_obj = MagicMock(
            propertyName="シャンボール浜名湖二号館",
            address="静岡県浜松市中央区",
            traffic="JR東海道本線 弁天島駅 徒歩15分",
            station1="弁天島",
            price=850000,
            tatemonoMenseki=45.0,
            tochiMenseki=0.0,
            senyuMenseki=45.0,
            grossYield=12.5,
            annualRent=106000,
            chikunengetsuStr="1985年4月",
            chikunengetsu=None,
            biko="オーナーチェンジ",
            pageUrl="https://www.homes.co.jp/mansion/b-1461180014380/",
        )
        valid_apt, reasons_apt = PropertyDataValidator.validate_property(apt_obj, "apartment")
        assert valid_apt, f"Homes apartment with yield should allow <100万円, got: {reasons_apt}"
