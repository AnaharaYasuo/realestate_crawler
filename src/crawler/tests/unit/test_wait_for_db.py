"""
Unit tests for wait_for_db.py fail-fast socket check and database readiness.
"""
from unittest.mock import MagicMock, patch

from scripts.debug_tools import wait_for_db


def test_wait_for_db_success():
    """Socket check and ensure_connection succeed on first attempt."""
    with patch("socket.create_connection") as mock_socket, \
         patch("scripts.debug_tools.wait_for_db.connection.ensure_connection") as mock_ensure:
        mock_socket.return_value.__enter__.return_value = MagicMock()

        result = wait_for_db.wait_for_db(max_retries=3, retry_interval=0.01)

        assert result is True
        assert mock_socket.call_count == 1
        assert mock_ensure.call_count == 1


def test_wait_for_db_socket_unreachable_fail_fast():
    """When socket is unreachable (OSError), it retries quickly without hanging on Django connection."""
    with patch("socket.create_connection", side_effect=OSError("Connection refused")) as mock_socket, \
         patch("scripts.debug_tools.wait_for_db.connection.ensure_connection") as mock_ensure:

        result = wait_for_db.wait_for_db(max_retries=3, retry_interval=0.01, socket_timeout=1.0)

        assert result is False
        assert mock_socket.call_count == 3
        # ensure_connection should never be called if socket fails!
        assert mock_ensure.call_count == 0


def test_wait_for_db_recovers_after_retry():
    """Socket initially fails, then succeeds on retry, followed by successful Django connection."""
    mock_sock_conn = MagicMock()
    with patch("socket.create_connection", side_effect=[OSError("Unreachable"), mock_sock_conn]) as mock_socket, \
         patch("scripts.debug_tools.wait_for_db.connection.ensure_connection") as mock_ensure:

        result = wait_for_db.wait_for_db(max_retries=3, retry_interval=0.01)

        assert result is True
        assert mock_socket.call_count == 2
        assert mock_ensure.call_count == 1
