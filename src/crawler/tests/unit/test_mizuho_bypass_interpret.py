# -*- coding: utf-8 -*-
"""Unit tests for MizuhoBypass detail status interpretation (Issue #317)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from package.utils.mizuho_bypass import (
    get_mizuho_page_html,
    interpret_mizuho_detail_fetch,
)


def test_interpret_404_returns_empty():
    assert interpret_mizuho_detail_fetch("https://x/", 404, "gone", "<html/>") == b""


def test_interpret_410_returns_empty():
    assert interpret_mizuho_detail_fetch("https://x/", 410, "gone", "<html/>") == b""


def test_interpret_403_status_raises():
    with pytest.raises(RuntimeError, match="WAF blocked"):
        interpret_mizuho_detail_fetch("https://x/", 403, "ok", "<html/>")


def test_interpret_403_title_raises():
    with pytest.raises(RuntimeError, match="WAF blocked"):
        interpret_mizuho_detail_fetch("https://x/", 200, "Error 403 Forbidden", "<html/>")


def test_interpret_other_4xx_raises():
    with pytest.raises(RuntimeError, match="Detail HTTP 418"):
        interpret_mizuho_detail_fetch("https://x/", 418, "teapot", "<html/>")


def test_interpret_success_encodes_html():
    out = interpret_mizuho_detail_fetch("https://x/", 200, "land", "<html>ok</html>")
    assert out == b"<html>ok</html>"


def test_interpret_none_status_success():
    out = interpret_mizuho_detail_fetch("https://x/", None, "land", "<html>x</html>")
    assert b"x" in out


@pytest.mark.asyncio
async def test_get_mizuho_page_html_uses_interpret_on_success():
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=[MagicMock(status=200), MagicMock(status=200)])
    page.wait_for_timeout = AsyncMock()
    page.title = AsyncMock(return_value="ok")
    page.content = AsyncMock(return_value="<html>detail</html>")

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.add_init_script = AsyncMock()
    context.close = AsyncMock()

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    playwright = MagicMock()
    playwright.chromium = chromium
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("package.utils.mizuho_bypass.async_playwright", return_value=playwright):
        html = await get_mizuho_page_html("https://www.mizuho-re.co.jp/buyers/property/1/")
    assert html == b"<html>detail</html>"


@pytest.mark.asyncio
async def test_get_mizuho_page_html_propagates_runtime_from_interpret():
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=[MagicMock(status=200), MagicMock(status=403)])
    page.wait_for_timeout = AsyncMock()
    page.title = AsyncMock(return_value="blocked")
    page.content = AsyncMock(return_value="<html/>")

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.add_init_script = AsyncMock()
    context.close = AsyncMock()

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    playwright = MagicMock()
    playwright.chromium = chromium
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("package.utils.mizuho_bypass.async_playwright", return_value=playwright):
        with pytest.raises(RuntimeError, match="WAF blocked"):
            await get_mizuho_page_html("https://www.mizuho-re.co.jp/buyers/property/1/")


@pytest.mark.asyncio
async def test_get_mizuho_page_html_wraps_unexpected_errors():
    playwright = MagicMock()
    playwright.__aenter__ = AsyncMock(side_effect=OSError("no browser"))
    playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("package.utils.mizuho_bypass.async_playwright", return_value=playwright):
        with pytest.raises(RuntimeError, match="Playwright failed"):
            await get_mizuho_page_html("https://www.mizuho-re.co.jp/buyers/property/1/")
