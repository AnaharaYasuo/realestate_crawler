from unittest.mock import MagicMock, patch

import pytest
import setup_env  # noqa: F401
from django.core.exceptions import ValidationError
from package.api import api as api_module
from package.api.sumifu_investment import ParseSumifuInvestApartmentDetailFuncAsync
from package.utils.failure_reporter import FailureReporter


class TestLocalLogScanDateFilter533:
    """Issue #533: ローカルログ走査は指定日付分のエラー行のみを集計する。"""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        self.base = tmp_path

    def test_undated_log_file_only_counts_lines_of_target_date(self):
        (self.base / "pipeline.log").write_text(
            "2026-07-18 13:37:43 ERROR: old failure\n"
            "2026-09-26 12:00:00 ERROR: target day failure\n"
            "2026-09-26 12:00:01 INFO: not an error\n"
            "2026-09-26 12:00:02 CRITICAL: target day critical\n"
            "Traceback ERROR without timestamp\n"
            "2026-09-27 00:00:00 ERROR: next day failure\n",
            encoding="utf-8",
        )

        errors = FailureReporter._scan_local_logs("20260926")

        entries = [e["log_entry"] for e in errors]
        assert entries == [
            "2026-09-26 12:00:00 ERROR: target day failure",
            "2026-09-26 12:00:02 CRITICAL: target day critical",
        ]
        assert [e["level"] for e in errors] == ["ERROR", "CRITICAL"]
        assert [e["line_number"] for e in errors] == [2, 4]

    def test_dated_log_file_counts_all_error_lines(self):
        (self.base / "run_20260926.log").write_text(
            "Traceback ERROR without timestamp\n"
            "2026-09-26 12:00:00 ERROR: target day failure\n"
            "2026-09-26 12:00:01 INFO: ok\n",
            encoding="utf-8",
        )

        errors = FailureReporter._scan_local_logs("20260926")

        assert [e["log_entry"] for e in errors] == [
            "Traceback ERROR without timestamp",
            "2026-09-26 12:00:00 ERROR: target day failure",
        ]

    def test_dated_log_file_excludes_lines_with_other_explicit_date(self):
        (self.base / "run_20260926.log").write_text(
            "2026-09-25 23:59:59 ERROR: carried over from previous day\n"
            "Traceback ERROR without timestamp\n"
            "2026-09-26 00:00:01 ERROR: target day failure\n",
            encoding="utf-8",
        )

        errors = FailureReporter._scan_local_logs("20260926")

        assert [e["log_entry"] for e in errors] == [
            "Traceback ERROR without timestamp",
            "2026-09-26 00:00:01 ERROR: target day failure",
        ]
        assert [e["line_number"] for e in errors] == [2, 3]

    def test_other_dated_log_file_is_filtered_by_line_date(self):
        (self.base / "run_20260925.log").write_text(
            "2026-09-25 23:59:59 ERROR: previous day\n",
            encoding="utf-8",
        )

        assert FailureReporter._scan_local_logs("20260926") == []

    def test_fetch_daily_failures_excludes_old_log_errors(self):
        (self.base / "pipeline.log").write_text(
            "2026-07-18 13:37:43 ERROR: old failure\n"
            "2026-09-26 12:00:00 ERROR: target day failure\n",
            encoding="utf-8",
        )

        with patch("package.utils.failure_reporter.get_storage_manager", side_effect=Exception("down")):
            manifest = FailureReporter.fetch_daily_failures(date_str="20260926")

        assert manifest["total_log_errors"] == 1
        assert manifest["log_errors"][0]["log_entry"] == "2026-09-26 12:00:00 ERROR: target day failure"


class TestValidationFailureReason533:
    """Issue #533: バリデーション失敗テレメトリに不正フィールド名を含める。"""

    def _make_item(self):
        item = MagicMock()
        item.pageUrl = "https://www.stepon.co.jp/mansion/detail_16133137/"
        item.propertyName = "ライオンズプラザ町屋"
        item.__class__.__name__ = "SumifuInvestmentApartment"
        item.full_clean.side_effect = ValidationError(
            {"tochiMensekiStr": ["This field cannot be blank."], "kaisu": ["This field cannot be blank."]}
        )
        return item

    def test_error_message_contains_invalid_fields(self):
        proc = object.__new__(ParseSumifuInvestApartmentDetailFuncAsync)
        item = self._make_item()

        with patch.object(api_module, "_sync_save_error_html_by_url") as mock_save:
            proc._save_item_record(item)

        mock_save.assert_called_once()
        url, model_name, reason = mock_save.call_args.args
        assert url == "https://www.stepon.co.jp/mansion/detail_16133137/"
        assert model_name == item.__class__.__name__
        assert reason == "Property Name: ライオンズプラザ町屋 | Invalid fields: kaisu, tochiMensekiStr"
        item.save.assert_not_called()

    def test_error_message_without_invalid_fields_keeps_legacy_format(self):
        proc = object.__new__(ParseSumifuInvestApartmentDetailFuncAsync)
        item = self._make_item()

        with patch.object(api_module, "_sync_save_error_html_by_url") as mock_save:
            proc._save_error_html_record(item)

        assert mock_save.call_args.args[2] == "Property Name: ライオンズプラザ町屋"

    def test_no_url_skips_saving(self):
        proc = object.__new__(ParseSumifuInvestApartmentDetailFuncAsync)
        item = self._make_item()
        item.pageUrl = ""

        with patch.object(api_module, "_sync_save_error_html_by_url") as mock_save:
            proc._save_error_html_record(item, ["kaisu"])

        mock_save.assert_not_called()
