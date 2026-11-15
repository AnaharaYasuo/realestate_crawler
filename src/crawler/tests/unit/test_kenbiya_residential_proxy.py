import asyncio
import os
import re
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from package.parser.kenbiyaParser import KenbiyaMansionParser, KenbiyaParserBase


def test_kenbiya_proxy_url_resolution(monkeypatch):
    """KenbiyaParserBase.get_proxy_url resolves KENBIYA_PROXY_URL, falls back to RESIDENTIAL_PROXY_URL, or None."""
    monkeypatch.delenv("KENBIYA_PROXY_URL", raising=False)
    monkeypatch.delenv("RESIDENTIAL_PROXY_URL", raising=False)
    assert KenbiyaParserBase.get_proxy_url() is None
    assert KenbiyaParserBase._build_playwright_proxy_config() is None

    monkeypatch.setenv("RESIDENTIAL_PROXY_URL", "http://res_user:res_pass@proxy.example.com:8000")
    assert KenbiyaParserBase.get_proxy_url() == "http://res_user:res_pass@proxy.example.com:8000"
    pw_cfg = KenbiyaParserBase._build_playwright_proxy_config()
    assert pw_cfg == {
        "server": "http://proxy.example.com:8000",
        "username": "res_user",
        "password": "res_pass",
    }

    # KENBIYA_PROXY_URL takes priority over RESIDENTIAL_PROXY_URL
    monkeypatch.setenv("KENBIYA_PROXY_URL", "http://ken_user:ken_pass@kenbiya-proxy.example.com:9000")
    assert KenbiyaParserBase.get_proxy_url() == "http://ken_user:ken_pass@kenbiya-proxy.example.com:9000"
    pw_cfg_priority = KenbiyaParserBase._build_playwright_proxy_config()
    assert pw_cfg_priority == {
        "server": "http://kenbiya-proxy.example.com:9000",
        "username": "ken_user",
        "password": "ken_pass",
    }


@pytest.mark.asyncio
async def test_get_content_passes_proxy_parameter_to_aiohttp(monkeypatch):
    """KenbiyaParserBase._getContent forwards the configured proxy URL to session.get."""
    proxy_endpoint = "http://ken_user:ken_pass@kenbiya-proxy.example.com:9000"
    monkeypatch.setenv("KENBIYA_PROXY_URL", proxy_endpoint)

    parser = KenbiyaMansionParser()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"<html>ok</html>"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_resp

    content = await parser._getContent(mock_session, "https://www.kenbiya.com/pp1/s/tokyo/test/")
    assert content == b"<html>ok</html>"

    mock_session.get.assert_called_once()
    called_kwargs = mock_session.get.call_args.kwargs
    assert called_kwargs.get("proxy") == proxy_endpoint


@pytest.mark.asyncio
async def test_get_content_without_proxy_has_no_proxy_param(monkeypatch):
    """When no proxy env var is set, session.get is called without 'proxy' argument."""
    monkeypatch.delenv("KENBIYA_PROXY_URL", raising=False)
    monkeypatch.delenv("RESIDENTIAL_PROXY_URL", raising=False)

    parser = KenbiyaMansionParser()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"<html>ok</html>"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_resp

    content = await parser._getContent(mock_session, "https://www.kenbiya.com/pp1/s/tokyo/test/")
    assert content == b"<html>ok</html>"

    mock_session.get.assert_called_once()
    called_kwargs = mock_session.get.call_args.kwargs
    assert "proxy" not in called_kwargs


@pytest.mark.asyncio
async def test_fetch_with_playwright_uses_proxy_and_routes_blocked(monkeypatch):
    """Playwright fallback launches with proxy config and registers route blocking for non-HTML assets."""
    proxy_endpoint = "http://puser:ppass@gate.proxy:8080"
    monkeypatch.setenv("KENBIYA_PROXY_URL", proxy_endpoint)

    parser = KenbiyaMansionParser()

    mock_page = AsyncMock()
    mock_page.content.return_value = "<html>playwright_ok</html>"

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright_mgr = MagicMock()
    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser
    mock_playwright_mgr.chromium = mock_chromium

    class DummyAsyncPlaywrightContext:
        async def __aenter__(self):
            return mock_playwright_mgr

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    with patch("playwright.async_api.async_playwright", return_value=DummyAsyncPlaywrightContext()):
        res = await parser._fetch_with_playwright("https://www.kenbiya.com/pp1/s/tokyo/403_target/")

    assert res == b"<html>playwright_ok</html>"
    mock_chromium.launch.assert_called_once()
    launch_kwargs = mock_chromium.launch.call_args.kwargs
    assert launch_kwargs.get("proxy") == {
        "server": "http://gate.proxy:8080",
        "username": "puser",
        "password": "ppass",
    }
    # Check route abortion registered
    mock_page.route.assert_called_once()
    route_pattern, route_handler = mock_page.route.call_args.args
    assert isinstance(route_pattern, re.Pattern)
    assert route_pattern.search("https://www.kenbiya.com/images/sample.jpg") is not None
    assert route_pattern.search("https://www.kenbiya.com/css/main.css") is not None

    # Test route handler blocks non-HTML resources
    mock_route = AsyncMock()
    mock_route.request.resource_type = "image"
    mock_route.request.url = "https://www.kenbiya.com/images/sample.jpg"
    await route_handler(mock_route)
    mock_route.abort.assert_called_once()

    # Test route handler allows document/fetch
    mock_route_doc = AsyncMock()
    mock_route_doc.request.resource_type = "document"
    mock_route_doc.request.url = "https://www.kenbiya.com/pp1/s/tokyo/test/"
    await route_handler(mock_route_doc)
    mock_route_doc.continue_.assert_called_once()
