"""
Tests for Issue #892: Crawler DB DNS Robustness and ML Train Import
"""
import socket
from unittest.mock import patch, MagicMock

from scripts.ops.run_all_crawlers import resolve_db_endpoint, DbLivenessMonitor


def test_resolve_db_endpoint_caches_ip(monkeypatch):
    """resolve_db_endpoint should resolve hostname to IP address to avoid continuous DNS lookups."""
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PORT", "3306")

    with patch("socket.gethostbyname", return_value="172.18.0.2") as mock_dns:
        host, port = resolve_db_endpoint()
        assert host == "172.18.0.2"
        assert port == 3306
        mock_dns.assert_called_once_with("db")


def test_resolve_db_endpoint_fallback_on_dns_failure(monkeypatch):
    """If initial DNS fails, resolve_db_endpoint should fallback to hostname gracefully."""
    monkeypatch.setenv("DB_HOST", "unresolvable-db")
    monkeypatch.setenv("DB_PORT", "3306")

    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        host, port = resolve_db_endpoint()
        assert host == "unresolvable-db"
        assert port == 3306


def test_db_liveness_monitor_uses_target_ip_without_dns_lookup():
    """DbLivenessMonitor should connect directly to resolved IP and not fail on subsequent DNS issues."""
    mock_connector = MagicMock()
    monitor = DbLivenessMonitor("172.18.0.2", 3306, connector=mock_connector)

    assert not monitor.is_lost()
    assert monitor.consecutive_failures == 0
    mock_connector.assert_called_once()
    assert mock_connector.call_args[0][0] == ("172.18.0.2", 3306)


def test_ml_train_module_import():
    """package.ml.train should be importable without ModuleNotFoundError."""
    import package.ml.train as train_module
    assert hasattr(train_module, "main")
    assert hasattr(train_module, "run_training")
