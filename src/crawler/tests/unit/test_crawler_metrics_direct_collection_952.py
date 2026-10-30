"""Unit tests for crawler metrics direct collection and connection recovery (Issue #952).

Verifies:
1. job_metrics records detail and skipped counts and exports to JSON atomically.
2. read_job_metrics reads saved metrics accurately.
3. resolve_job_counts prioritizes JSON metrics and bypasses DB COUNT(*) query.
4. resolve_job_counts gracefully falls back to DB COUNT(*) when metrics file is missing.
5. exit_code == 0 with DB timeout/0 returns success and avoids false alert.
6. send_recommendations and run_daily_prediction_diagnostics close connections cleanly.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from package.utils.job_metrics import (
    export_job_metrics,
    get_current_metrics,
    read_job_metrics,
    record_detail_processed,
    record_item_skipped,
    reset_metrics,
)
from scripts.ops.run_all_crawlers import resolve_job_counts


@pytest.fixture(autouse=True)
def _clean_metrics():
    reset_metrics()
    yield
    reset_metrics()


def test_job_metrics_record_and_get():
    reset_metrics()
    record_detail_processed(3)
    record_item_skipped(5)
    detail, skipped = get_current_metrics()
    assert detail == 3
    assert skipped == 5


def test_export_and_read_job_metrics(tmp_path: Path):
    test_date = "20261016"
    test_comp = "testrearie"
    test_ptype = "kodate"

    with patch("package.utils.job_metrics._get_metrics_dir", return_value=tmp_path):
        record_detail_processed(42)
        record_item_skipped(7)
        saved_file = export_job_metrics(test_comp, test_ptype, run_date=test_date)
        assert saved_file is not None
        assert saved_file.exists()

        counts = read_job_metrics(test_comp, test_ptype, run_date=test_date)
        assert counts is not None
        assert counts == (42, 7, 49, False)


def test_resolve_job_counts_prefers_metrics_file():
    with patch("scripts.ops.run_all_crawlers.read_job_metrics", return_value=(10, 2, 12, False)) as mock_read:
        with patch("scripts.ops.run_all_crawlers.get_count_for_job") as mock_db:
            detail, skip, tot, is_empty, from_file = resolve_job_counts("rearie", "kodate", None)
            assert from_file is True
            assert is_empty is False
            assert (detail, skip, tot) == (10, 2, 12)
            mock_read.assert_called_once()
            mock_db.assert_not_called()  # DB COUNT query must be bypassed!


def test_resolve_job_counts_fallback_to_db_when_no_file():
    with patch("scripts.ops.run_all_crawlers.read_job_metrics", return_value=None):
        with patch("scripts.ops.run_all_crawlers.get_count_for_job", return_value=(5, 1, 6)) as mock_db:
            detail, skip, tot, is_empty, from_file = resolve_job_counts("rearie", "kodate", datetime.datetime.now(datetime.timezone.utc))
            assert from_file is False
            assert is_empty is False
            assert (detail, skip, tot) == (5, 1, 6)
            mock_db.assert_called_once()


def test_resolve_job_counts_fallback_when_db_returns_none():
    with patch("scripts.ops.run_all_crawlers.read_job_metrics", return_value=None):
        with patch("scripts.ops.run_all_crawlers.get_count_for_job", return_value=(None, None, None)):
            detail, skip, tot, is_empty, from_file = resolve_job_counts("rearie", "kodate", datetime.datetime.now(datetime.timezone.utc))
            assert from_file is False
            assert is_empty is False
            assert (detail, skip, tot) == (0, 0, 0)


def test_send_recommendations_resets_db_connection():
    from scripts.ops.send_recommendations import send_recommendations
    with patch("scripts.ops.send_recommendations.close_old_connections") as mock_close_old, \
         patch("scripts.ops.send_recommendations.connections.close_all") as mock_close_all, \
         patch("scripts.ops.send_recommendations.bound_mysql_timeouts") as mock_timeouts, \
         patch("scripts.ops.send_recommendations._fetch_recommendation_candidates", return_value=[]), \
         patch("scripts.ops.send_recommendations._notify_status"):
        send_recommendations()
        mock_close_old.assert_called_once()
        mock_close_all.assert_called_once()
        mock_timeouts.assert_called_once()


def test_run_daily_prediction_diagnostics_resets_db_connection():
    from scripts.ops.run_daily_prediction_diagnostics import run_diagnostics
    with patch("scripts.ops.run_daily_prediction_diagnostics.close_old_connections") as mock_close_old, \
         patch("scripts.ops.run_daily_prediction_diagnostics.connections.close_all") as mock_close_all, \
         patch("scripts.ops.run_daily_prediction_diagnostics.bound_mysql_timeouts") as mock_timeouts, \
         patch("scripts.ops.run_daily_prediction_diagnostics.PropertyEvaluation.objects.filter") as mock_filter:
        mock_filter.return_value.count.return_value = 0
        run_diagnostics(dry_run=True)
        mock_close_old.assert_called_once()
        mock_close_all.assert_called_once()
        mock_timeouts.assert_called_once()
