"""
Tests for Issue #892: Crawler DB DNS Robustness and ML Train Import
"""
import socket
from unittest.mock import patch, MagicMock

from scripts.ops.run_all_crawlers import resolve_db_endpoint, DbLivenessMonitor


def test_resolve_db_endpoint_returns_host_and_port(monkeypatch):
    """resolve_db_endpoint returns host and port from settings or environment."""
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PORT", "3306")
    host, port = resolve_db_endpoint()
    assert host == "db"
    assert port == 3306


def test_db_liveness_monitor_resolves_and_caches_ip():
    """DbLivenessMonitor should resolve target IP initially with timeout and use it."""
    mock_connector = MagicMock()
    with patch("socket.gethostbyname", return_value="172.18.0.2") as mock_dns:
        monitor = DbLivenessMonitor("db", 3306, connector=mock_connector)
        assert monitor.target_ip == "172.18.0.2"
        assert not monitor.is_lost()
        mock_connector.assert_called_once_with(("172.18.0.2", 3306), timeout=3.0)


def test_db_liveness_monitor_re_resolves_ip_on_failure():
    """DbLivenessMonitor should re-resolve IP when connection fails before incrementing consecutive failures."""
    calls = []

    def mock_conn(addr, timeout):
        calls.append(addr)
        if addr == ("172.18.0.2", 3306):
            raise OSError("Connection refused")
        return MagicMock()

    with patch("socket.gethostbyname", side_effect=["172.18.0.2", "172.18.0.3"]):
        monitor = DbLivenessMonitor("db", 3306, connector=mock_conn)
        assert monitor.target_ip == "172.18.0.2"
        # First probe triggers failure on old IP, then successfully re-resolves and connects to new IP
        monitor._probe()
        assert monitor.target_ip == "172.18.0.3"
        assert monitor.consecutive_failures == 0


def test_ml_train_module_import():
    """package.ml.train should be importable without ModuleNotFoundError."""
    import package.ml.train as train_module
    assert hasattr(train_module, "main")
    assert hasattr(train_module, "run_training")
