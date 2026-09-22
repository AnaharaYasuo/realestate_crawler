# -*- coding: utf-8 -*-
"""Unit tests for mizuho_bypass.get_mizuho_page_html (Issue #317)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from package.utils import mizuho_bypass


def _playwright_stack(status=200, title="ok", content="<html>ok</html>", fail_close=False):
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=[MagicMock(status=200), MagicMock(status=status)])
    page.title = AsyncMock(return_value=title)
    page.content = AsyncMock(return_value=content)
    page.wait_for_timeout = AsyncMock()

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.add_init_script = AsyncMock()
    if fail_close:
        context.close = AsyncMock(side_effect=Exception("ctx close"))
    else:
        context.close = AsyncMock()

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    if fail_close:
        browser.close = AsyncMock(side_effect=Exception("browser close"))
    else:
        browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)
    playwright = MagicMock()
    playwright.chromium = chromium

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=playwright)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, page


@pytest.mark.asyncio
async def test_get_mizuho_page_html_success():
    cm, _ = _playwright_stack(status=200, content="<html>detail</html>")
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        html = await mizuho_bypass.get_mizuho_page_html(
            "https://www.mizuho-re.co.jp/buyers/property/1/"
        )
    assert b"detail" in html


@pytest.mark.asyncio
async def test_get_mizuho_page_html_404_returns_empty():
    cm, _ = _playwright_stack(status=404)
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        html = await mizuho_bypass.get_mizuho_page_html(
            "https://www.mizuho-re.co.jp/buyers/property/1/"
        )
    assert html == b""


@pytest.mark.asyncio
async def test_get_mizuho_page_html_403_raises():
    cm, _ = _playwright_stack(status=403, title="403 Forbidden")
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        with pytest.raises(RuntimeError, match="WAF blocked"):
            await mizuho_bypass.get_mizuho_page_html(
                "https://www.mizuho-re.co.jp/buyers/property/1/"
            )


@pytest.mark.asyncio
async def test_get_mizuho_page_html_500_raises():
    cm, _ = _playwright_stack(status=500, title="error")
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        with pytest.raises(RuntimeError, match="Detail HTTP 500"):
            await mizuho_bypass.get_mizuho_page_html(
                "https://www.mizuho-re.co.jp/buyers/property/1/"
            )


@pytest.mark.asyncio
async def test_get_mizuho_page_html_playwright_exception_wraps():
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=Exception("launch failed"))
    cm.__aexit__ = AsyncMock(return_value=None)
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        with pytest.raises(RuntimeError, match="Playwright failed"):
            await mizuho_bypass.get_mizuho_page_html(
                "https://www.mizuho-re.co.jp/buyers/property/1/"
            )


@pytest.mark.asyncio
async def test_get_mizuho_page_html_close_errors_are_swallowed():
    cm, _ = _playwright_stack(status=200, fail_close=True)
    with patch("package.utils.mizuho_bypass.async_playwright", return_value=cm):
        html = await mizuho_bypass.get_mizuho_page_html(
            "https://www.mizuho-re.co.jp/buyers/property/1/"
        )
    assert b"ok" in html
