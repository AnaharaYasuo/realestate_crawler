"""Unit tests for Issue #1887: send_recommendations candidate query Error 2013 resilience."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.db import OperationalError


def test_execute_candidate_query_with_retry_recovers_from_error_2013():
    """Verify Issue #1887: transient OperationalError (2013) triggers connection reset and retry."""
    from scripts.ops import send_recommendations as sr

    rec = MagicMock(id=42)
    attempts = {"count": 0}

    def _qs_factory():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(2013, "Lost connection to server during query")
        return [rec]

    with (
        patch.object(sr, "close_old_connections") as mock_close_old,
        patch.object(sr.connections, "close_all") as mock_close_all,
        patch.object(sr, "bound_mysql_timeouts") as mock_timeouts,
        patch.object(sr.time, "sleep"),
    ):
        rows = sr._execute_candidate_query_with_retry(_qs_factory, label="property_type=mansion")

    assert rows == [rec]
    assert attempts["count"] == 2
    mock_close_old.assert_called_once()
    mock_close_all.assert_called_once()
    mock_timeouts.assert_called_once()


def test_execute_candidate_query_with_retry_returns_empty_after_exhaustion():
    """Verify Issue #1887: persistent OperationalError does not crash the entire recommendation batch."""
    from scripts.ops import send_recommendations as sr

    def _failing_qs():
        raise OperationalError(2013, "Lost connection to server during query")

    with (
        patch.object(sr, "close_old_connections"),
        patch.object(sr.connections, "close_all"),
        patch.object(sr, "bound_mysql_timeouts"),
        patch.object(sr.time, "sleep"),
    ):
        rows = sr._execute_candidate_query_with_retry(
            _failing_qs, label="property_type=apartment", max_attempts=2
        )

    assert rows == []


def test_recommendation_lookback_days_constant_is_bounded():
    """Verify Issue #1887: candidate query lookback window is bounded to prevent full index scans."""
    from scripts.ops import send_recommendations as sr

    assert 7 <= sr.RECOMMENDATION_LOOKBACK_DAYS <= 60
