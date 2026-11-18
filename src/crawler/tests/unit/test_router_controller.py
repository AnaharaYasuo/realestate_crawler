import pytest
from unittest.mock import patch, MagicMock
from package.utils import router_controller

def test_router_controller_skips_when_no_password(monkeypatch):
    monkeypatch.delenv("GL_ROUTER_PASSWORD", raising=False)
    res = router_controller.reconnect_router_pppoe()
    assert res["success"] is False
    assert res["skipped"] is True
    assert res["reason"] == "no_password"

def test_router_controller_skips_on_cloud(monkeypatch):
    monkeypatch.setenv("GL_ROUTER_PASSWORD", "dummy_pass")
    monkeypatch.setenv("IS_CLOUD", "true")
    res = router_controller.reconnect_router_pppoe()
    assert res["success"] is False
    assert res["skipped"] is True
    assert res["reason"] == "cloud_environment"

def test_ensure_router_pppoe_reconnected_safe(monkeypatch):
    monkeypatch.delenv("GL_ROUTER_PASSWORD", raising=False)
    # Should not raise exception
    router_controller.ensure_router_pppoe_reconnected()

    monkeypatch.setenv("GL_ROUTER_PASSWORD", "dummy_pass")
    with patch.object(router_controller, "reconnect_router_pppoe", side_effect=Exception("network down")):
        # Should gracefully catch and not raise
        router_controller.ensure_router_pppoe_reconnected()
