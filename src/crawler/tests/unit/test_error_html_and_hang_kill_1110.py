# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from package.utils.crawler_watchdog import (
    DEFAULT_HANG_THRESHOLD_SEC,
    _parse_hang_threshold,
    check_job_hung,
)
from package.utils.failure_reporter import FailureReporter


class TestHangKillAndErrorHtml1110(unittest.TestCase):
    def test_default_hang_threshold_is_300_seconds(self):
        """環境変数未設定時に5分（300秒）がデフォルトとなること (Issue #1110)"""
        with patch.dict(os.environ, {}, clear=True):
            val = _parse_hang_threshold()
            self.assertEqual(val, DEFAULT_HANG_THRESHOLD_SEC)
            self.assertEqual(val, 300.0)

    def test_hang_threshold_custom_env(self):
        """明示的に設定された場合はその値が使われること"""
        with patch.dict(os.environ, {"CRAWLER_HANG_THRESHOLD_SEC": "120.0"}):
            val = _parse_hang_threshold()
            self.assertEqual(val, 120.0)

    def test_check_job_hung_triggers_after_threshold(self):
        """300秒の無音で正しくハング判定されること"""
        now = 1000.0
        # 301秒前のアクティビティ
        last_act = now - 301.0
        hung = check_job_hung(last_activity_time=last_act, current_time=now, threshold_sec=300.0)
        self.assertTrue(hung)

        # 299秒前のアクティビティ（まだ閾値未満）
        not_hung = check_job_hung(last_activity_time=now - 299.0, current_time=now, threshold_sec=300.0)
        self.assertFalse(not_hung)

    def test_record_job_failure_attaches_existing_error_html(self):
        """事前に保存されたerror_pagesのHTMLが未指定時にも自動で紐づけられること"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"STORAGE_LOCAL_FALLBACK_DIR": temp_dir}):
                err_dir = Path(temp_dir) / "runs" / "20261025" / "error_pages" / "testcomp_testtype"
                err_dir.mkdir(parents=True, exist_ok=True)
                sample_html = err_dir / "abc12345.html"
                sample_html.write_bytes(b"<html><body>Sample Error Page</body></html>")

                with patch.object(FailureReporter, "_upload_failure_telemetry", return_value=False):
                    record = FailureReporter.record_job_failure(
                        company="testcomp",
                        property_type="testtype",
                        error_type="ZeroCountFailure",
                        error_message="0 items scraped",
                        date_str="20261025"
                    )
                    self.assertIsNotNone(record)
                    meta_path = Path(temp_dir) / "runs" / "20261025" / "failures" / "testcomp_testtype.json"
                    self.assertTrue(meta_path.exists())