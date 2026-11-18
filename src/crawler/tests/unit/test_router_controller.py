import os
import sys
from unittest.mock import MagicMock, patch

from package.utils import router_controller


def test_disconnect_router_pppoe_skips_without_password(monkeypatch):
    monkeypatch.delenv("GL_ROUTER_PASSWORD", raising=False)
    res = router_controller.disconnect_router_pppoe(password=None)
    assert res == {"success": False, "error": None}


def test_disconnect_router_pppoe_skips_in_cloud(monkeypatch):
    monkeypatch.setenv("GL_ROUTER_PASSWORD", "secret")
    monkeypatch.setenv("IS_CLOUD", "1")
    res = router_controller.disconnect_router_pppoe()
    assert res == {"success": False, "error": None}


def test_disconnect_router_pppoe_executes_ifdown(monkeypatch):
    monkeypatch.setenv("GL_ROUTER_PASSWORD", "secret")
    monkeypatch.delenv("IS_CLOUD", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)

    mock_page = MagicMock()
    mock_page.evaluate.return_value = {"code": 0}
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_pw

    mock_sync_pw_mod = MagicMock()
    mock_sync_pw_mod.sync_playwright.return_value = mock_cm

    with patch.dict(sys.modules, {"playwright.sync_api": mock_sync_pw_mod}):
        res = router_controller.disconnect_router_pppoe(host="192.168.8.1", password="secret")

    assert res["success"] is True
    mock_page.evaluate.assert_called_once()


def test_ensure_router_pppoe_disconnected_calls_disconnect(monkeypatch):
    monkeypatch.setenv("GL_ROUTER_PASSWORD", "secret")
    with patch.object(router_controller, "disconnect_router_pppoe", return_value={"success": True}) as mock_disc:
        router_controller.ensure_router_pppoe_disconnected()
    mock_disc.assert_called_once()


def test_ensure_router_pppoe_disconnected_handles_exception(monkeypatch):
    monkeypatch.setenv("GL_ROUTER_PASSWORD", "secret")
    with patch.object(router_controller, "disconnect_router_pppoe", side_effect=RuntimeError("boom")):
        # Should not raise
        router_controller.ensure_router_pppoe_disconnected()
