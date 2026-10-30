"""Unit tests for Phase 4: Failure Observability & Field Fill-Rate Drift Telemetry (Issue #1151)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import setup_env  # noqa: F401
from package.utils.failure_reporter import FailureReporter
from package.utils.job_metrics import compute_field_fill_rates, export_job_metrics
from package.utils.newrelic_helper import record_field_fill_rate_event


class TestPhase4Observability:
    @pytest.fixture(autouse=True)
    def _isolate_fallback_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        self.tmp_path = tmp_path

    def test_record_job_failure_appends_multiple_failures_and_captures_all_html_paths(self):
        """Multiple failures in the same job run are appended rather than overwritten (Last-Write-Wins eliminated)."""
        err_dir = self.tmp_path / "runs" / "20261030" / "error_pages" / "nomura_mansion"
        err_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(3):
            (err_dir / f"err_{idx}.html").write_bytes(f"<html>err {idx}</html>".encode())

        with patch("package.utils.failure_reporter.get_storage_manager", side_effect=RuntimeError("offline")):
            rec1 = FailureReporter.record_job_failure(
                company="nomura",
                property_type="mansion",
                error_type="ParseHtmlError",
                error_message="First detail failure",
                target_url="https://www.nomu.com/mansion/1",
                parent_list_url="https://www.nomu.com/mansion/list?page=1",
                http_status=200,
                date_str="20261030",
            )
            rec2 = FailureReporter.record_job_failure(
                company="nomura",
                property_type="mansion",
                error_type="ZeroCountFailure",
                error_message="Job exited with 0 items",
                target_url="https://www.nomu.com/mansion/2",
                parent_list_url="https://www.nomu.com/mansion/list?page=2",
                http_status=403,
                date_str="20261030",
            )

        assert rec1["failure_count"] == 1
        assert rec2["failure_count"] == 2
        assert len(rec2["failures"]) == 2
        assert rec2["failures"][0]["error_type"] == "ParseHtmlError"
        assert rec2["failures"][0]["parent_list_url"] == "https://www.nomu.com/mansion/list?page=1"
        assert rec2["failures"][1]["error_type"] == "ZeroCountFailure"
        assert rec2["failures"][1]["http_status"] == 403
        assert len(rec2["local_error_html_paths"]) >= 3

    def test_compute_field_fill_rates_and_export(self, monkeypatch):
        """compute_field_fill_rates calculates accurate ratios for both objects and dicts."""
        items = [
            SimpleNamespace(
                propertyName="パークマンション赤坂",
                price=128000000,
                address="東京都港区赤坂",
                station1="赤坂",
                ensen1="東京メトロ千代田線",
                toho1=5,
            ),
            SimpleNamespace(
                propertyName="プラウド六本木",
                price=98000000,
                address="東京都港区六本木",
                station1="",
                ensen1=None,
                toho1=0,
            ),
        ]
        rates = compute_field_fill_rates(items)
        assert rates["propertyName"] == 1.0
        assert rates["price"] == 1.0
        assert rates["address"] == 1.0
        assert rates["station1"] == 0.5
        assert rates["ensen1"] == 0.5
        assert rates["toho1"] == 0.5

        monkeypatch.chdir(self.tmp_path)
        path = export_job_metrics(
            company="nomura",
            property_type="mansion",
            detail_cnt=2,
            skipped_cnt=0,
            run_date="20261030",
            field_fill_rates=rates,
        )
        assert path is not None and path.exists()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["field_fill_rates"]["station1"] == 0.5

    def test_record_field_fill_rate_event_detects_drift(self, monkeypatch):
        """record_field_fill_rate_event flags degraded_fields when fill rate drops below threshold."""
        monkeypatch.setenv("NEW_RELIC_LICENSE_KEY", "dummy-key")
        mock_agent = MagicMock()
        fill_rates = {
            "propertyName": 1.0,
            "price": 1.0,
            "address": 0.95,
            "station1": 0.1,
            "ensen1": 0.1,
        }
        with patch("package.utils.newrelic_helper._get_agent", return_value=mock_agent):
            ok = record_field_fill_rate_event(
                site_name="nomura",
                property_type="mansion",
                fill_rates=fill_rates,
                item_count=20,
                low_fill_threshold=0.5,
            )
        assert ok is True
        mock_agent.record_custom_event.assert_called_once()
        event_name, payload = mock_agent.record_custom_event.call_args.args[:2]
        assert event_name == "FieldFillRateEvent"
        assert payload["has_drift"] is True
        assert payload["degraded_fields"] == "ensen1,station1"
        assert payload["min_fill_rate"] == 0.1
        assert payload["fill_rate_station1"] == 0.1
