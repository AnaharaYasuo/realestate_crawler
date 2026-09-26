import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
import setup_env  # noqa: F401
from package.utils.failure_reporter import (
    FailureReporter,
    generate_auto_heal_trigger_message,
)


class TestGcsFailureTelemetry466:
    """Issue #466: GCS Real-time failure telemetry and auto-heal integration tests."""

    def test_record_job_failure_with_gcs_and_html(self, tmp_path):
        """Test recording failure uploads metadata JSON and raw HTML."""
        mock_storage = MagicMock()
        mock_storage.bucket_name = "test-bucket"
        mock_storage.upload_bytes.return_value = "gs://test-bucket/test_path"

        with patch("package.utils.failure_reporter.get_storage_manager", return_value=mock_storage):
            rec = FailureReporter.record_job_failure(
                company="nomura",
                property_type="mansion",
                error_type="SelectorMismatch",
                error_message="table.detail_table not found",
                target_url="https://www.nomu.com/mansion/test",
                exit_code=1,
                traceback_str="Traceback dummy",
                raw_html=b"<html><body>dummy error page</body></html>",
                duration_seconds=16,
                task_index=1,
                task_count=8,
                date_str="20260926"
            )

        assert rec["company"] == "nomura"
        assert rec["property_type"] == "mansion"
        assert rec["error_type"] == "SelectorMismatch"
        assert rec["exit_code"] == 1
        assert "nomura_mansion.json" in rec["metadata_key"]
        assert rec["gcs_html_path"] is not None
        assert mock_storage.upload_bytes.call_count == 2
        expected_html_key = (
            "runs/20260926/error_pages/nomura_mansion/"
            f"{hashlib.sha256(b'https://www.nomu.com/mansion/test').hexdigest()[:16]}.html"
        )
        html_calls = [
            c for c in mock_storage.upload_bytes.call_args_list
            if c.kwargs.get("content_type") == "text/html"
        ]
        assert len(html_calls) == 1
        assert html_calls[0].args[0] == b"<html><body>dummy error page</body></html>"
        assert html_calls[0].args[1] == expected_html_key

    def test_record_job_failure_fallback_without_gcs(self, tmp_path, monkeypatch):
        """Test fallback when storage upload fails or is in fallback mode."""
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))

        with patch("package.utils.failure_reporter.get_storage_manager", side_effect=Exception("Storage unavailable")):
            rec = FailureReporter.record_job_failure(
                company="mitsui",
                property_type="kodate",
                error_type="HttpBlocked403",
                error_message="HTTP 403 Forbidden",
                target_url="https://www.rehouse.co.jp/test",
                exit_code=1,
                raw_html=b"<html>Blocked</html>",
                date_str="20260926"
            )

        assert rec["company"] == "mitsui"
        assert rec["error_type"] == "HttpBlocked403"
        # Check local fallback file exists
        fallback_file = tmp_path / "runs" / "20260926" / "failures" / "mitsui_kodate.json"
        assert fallback_file.exists()
        with open(fallback_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["company"] == "mitsui"

    def test_fetch_daily_failures_aggregates_multiple_jobs(self):
        """Test fetch_daily_failures aggregates all job failures into one manifest."""
        mock_storage = MagicMock()
        mock_storage.list_files.return_value = [
            "runs/20260926/failures/nomura_mansion.json",
            "runs/20260926/failures/mitsui_kodate.json",
            "runs/20260926/failures/sekisui_kodate.json",
        ]
        
        sample_nomura = json.dumps({"company": "nomura", "property_type": "mansion", "error_type": "SelectorMismatch"})
        sample_mitsui = json.dumps({"company": "mitsui", "property_type": "kodate", "error_type": "HttpBlocked403"})
        sample_sekisui = json.dumps({"company": "sekisui", "property_type": "kodate", "error_type": "ZeroCountFailure"})

        def mock_read_file(key):
            if "nomura" in key: return sample_nomura
            if "mitsui" in key: return sample_mitsui
            return sample_sekisui

        mock_storage.read_text.side_effect = mock_read_file

        with patch("package.utils.failure_reporter.get_storage_manager", return_value=mock_storage):
            manifest = FailureReporter.fetch_daily_failures(date_str="20260926")

        assert manifest["date"] == "20260926"
        assert manifest["total_failures"] == 3
        assert len(manifest["failures"]) == 3
        companies = [f["company"] for f in manifest["failures"]]
        assert "nomura" in companies
        assert "mitsui" in companies
        assert "sekisui" in companies

    def test_generate_auto_heal_trigger_message(self):
        """Test Slack @DevAgent zero-touch auto-heal trigger format."""
        msg = generate_auto_heal_trigger_message(
            date_str="20260926",
            failed_count=4,
            failed_jobs=[("nomura", "mansion"), ("mitsui", "kodate"), ("sekisui", "kodate"), ("mitsui", "invest_apartment")]
        )

        assert "@DevAgent" in msg
        assert "20260926" in msg
        assert "4 件の異常" in msg
        assert "fetch_run_failures.py" in msg
        assert "nomura - mansion" in msg
        assert "mitsui - kodate" in msg

    def test_base_parser_save_error_html_calls_failure_reporter(self, tmp_path, monkeypatch):
        """Test baseParser.save_error_html triggers FailureReporter.record_job_failure."""
        from package.parser.nomuraParser import NomuraMansionParser

        parser = NomuraMansionParser("")
        with patch.object(FailureReporter, "record_job_failure") as mock_record:
            parser.save_error_html(
                url="https://www.nomu.com/mansion/test",
                content=b"<html>error</html>",
                reason="Test reason"
            )
            mock_record.assert_called_once()
            kwargs = mock_record.call_args.kwargs
            assert kwargs["company"] == "nomura"
            assert kwargs["property_type"] == "mansion"
            assert kwargs["error_type"] == "ParseHtmlError"
            assert kwargs["error_message"] == "Test reason"
            assert kwargs["raw_html"] == b"<html>error</html>"

    def test_fetch_run_failures_cli_main(self, capsys):
        """Test CLI main function in fetch_run_failures.py."""
        from scripts.debug_tools.fetch_run_failures import main

        sample_manifest = {
            "date": "20260926",
            "total_failures": 1,
            "failures": [{
                "company": "nomura",
                "property_type": "mansion",
                "error_type": "SelectorMismatch",
                "error_message": "table missing",
                "target_url": "https://test.com",
                "parser_file": "src/crawler/package/parser/nomuraParser.py",
                "gcs_html_path": "gs://test/html"
            }]
        }

        with patch.object(FailureReporter, "fetch_daily_failures", return_value=sample_manifest):
            with patch("sys.argv", ["fetch_run_failures.py", "--date", "20260926"]):
                main()
                captured = capsys.readouterr()
                data = json.loads(captured.out)
                assert data["total_failures"] == 1
                assert data["failures"][0]["company"] == "nomura"

            with patch("sys.argv", ["fetch_run_failures.py", "--date", "20260926", "--summary"]):
                main()
                captured = capsys.readouterr()
                assert "=== Crawling Failures Summary for 20260926 ===" in captured.out
                assert "nomura - mansion" in captured.out

    def test_fetch_run_failures_cli_storage_error_nonzero_exit(self, capsys):
        """Test CLI exits with code 1 when storage fails and 0 fallback records exist."""
        from scripts.debug_tools.fetch_run_failures import main

        error_manifest = {
            "date": "20260926",
            "total_failures": 0,
            "storage_error": "ConnectionTimeout",
            "failures": []
        }

        with (
            patch.object(FailureReporter, "fetch_daily_failures", return_value=error_manifest),
            patch("sys.argv", ["fetch_run_failures.py", "--date", "20260926"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to retrieve telemetry from storage" in captured.err

    def test_storage_manager_list_files_pagination(self):
        """Test ObjectStorageManager.list_files handles pagination correctly."""
        from package.utils.storage import ObjectStorageManager

        sm = ObjectStorageManager()
        page1 = {
            "Contents": [{"Key": "runs/20260926/failures/job1.json"}],
            "IsTruncated": True,
            "NextContinuationToken": "token123"
        }
        page2 = {
            "Contents": [{"Key": "runs/20260926/failures/job2.json"}],
            "IsTruncated": False
        }

        sm.s3_client = MagicMock()
        sm.s3_client.list_objects_v2.side_effect = [page1, page2]

        keys = sm.list_files(prefix="runs/20260926/failures/")
        assert len(keys) == 2
        assert keys == ["runs/20260926/failures/job1.json", "runs/20260926/failures/job2.json"]
        assert sm.s3_client.list_objects_v2.call_count == 2

    def test_fetch_daily_failures_includes_log_file_errors(self, tmp_path, monkeypatch):
        """Test fetch_daily_failures scans and aggregates log file errors."""
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        
        log_file = tmp_path / "run_20260926.log"
        log_file.write_text(
            "2026-09-26 12:00:00 [INFO] Starting crawler\n"
            "2026-09-26 12:00:05 [ERROR] [1] Crawl job FAILED for sumifu - tochi. Exit Code: 0, Scraped: 0 items, Error: 0 items scraped (Zero count failure)\n"
            "2026-09-26 12:00:10 [CRITICAL] Database connection lost\n",
            encoding="utf-8"
        )

        with patch("package.utils.failure_reporter.get_storage_manager", side_effect=Exception("Storage unavailable")):
            manifest = FailureReporter.fetch_daily_failures(date_str="20260926")

        assert manifest["date"] == "20260926"
        assert manifest["total_log_errors"] == 2
        assert len(manifest["log_errors"]) == 2
        levels = [e["level"] for e in manifest["log_errors"]]
        assert "ERROR" in levels
        assert "CRITICAL" in levels
        assert "sumifu - tochi" in manifest["log_errors"][0]["log_entry"]


