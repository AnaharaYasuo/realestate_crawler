# -*- coding: utf-8 -*-
"""Mizuho detail WAF bypass (Issue #317)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from package.parser.baseParser import (
    ListingEndedException,
    LoadPropertyPageException,
    ServerBusyException,
    ServerDownException,
)
from package.parser.mizuhoParser import MizuhoTochiParser


def _session_with_status(status: int, body: bytes = b"ok") -> AsyncMock:
    session = AsyncMock()
    resp = AsyncMock()
    resp.status = status
    resp.read = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    session.get = MagicMock(return_value=resp)
    return session


@pytest.mark.asyncio
async def test_mizuho_get_content_falls_back_to_playwright_on_404():
    parser = MizuhoTochiParser()
    session = _session_with_status(404)
    fake_html = b"<html><title>land</title><body>ok</body></html>"
    with patch(
        "package.utils.mizuho_bypass.get_mizuho_page_html",
        new_callable=AsyncMock,
        return_value=fake_html,
    ) as bypass:
        content = await parser._getContent(
            session, "https://www.mizuho-re.co.jp/buyers/property/000000949590/"
        )
    assert content == fake_html
    bypass.assert_awaited_once()


@pytest.mark.asyncio
async def test_mizuho_get_content_200_returns_body():
    parser = MizuhoTochiParser()
    body = b"<html>ok</html>"
    session = _session_with_status(200, body)
    assert await parser._getContent(session, "https://www.mizuho-re.co.jp/x/") == body


@pytest.mark.asyncio
async def test_mizuho_playwright_empty_on_404_is_listing_ended():
    parser = MizuhoTochiParser()
    session = _session_with_status(404)
    with patch(
        "package.utils.mizuho_bypass.get_mizuho_page_html",
        new_callable=AsyncMock,
        return_value=b"",
    ):
        with pytest.raises(ListingEndedException):
            await parser._getContent(
                session, "https://www.mizuho-re.co.jp/buyers/property/000000949590/"
            )


@pytest.mark.asyncio
async def test_mizuho_playwright_waf_block_propagates_as_load_error():
    parser = MizuhoTochiParser()
    session = _session_with_status(403)
    with patch(
        "package.utils.mizuho_bypass.get_mizuho_page_html",
        new_callable=AsyncMock,
        side_effect=RuntimeError("WAF blocked"),
    ):
        with pytest.raises(LoadPropertyPageException):
            await parser._getContent(
                session, "https://www.mizuho-re.co.jp/buyers/property/000000949590/"
            )


@pytest.mark.asyncio
async def test_mizuho_server_busy_on_503():
    parser = MizuhoTochiParser()
    session = _session_with_status(503)
    with pytest.raises(ServerBusyException):
        await parser._getContent(session, "https://www.mizuho-re.co.jp/buyers/property/1/")


@pytest.mark.asyncio
async def test_mizuho_empty_bypass_on_403_is_load_error():
    parser = MizuhoTochiParser()
    session = _session_with_status(403)
    with patch(
        "package.utils.mizuho_bypass.get_mizuho_page_html",
        new_callable=AsyncMock,
        return_value=b"",
    ):
        with pytest.raises(LoadPropertyPageException):
            await parser._getContent(session, "https://www.mizuho-re.co.jp/x/")


@pytest.mark.asyncio
async def test_mizuho_repeated_timeouts_raise_server_down():
    parser = MizuhoTochiParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 2
    session = AsyncMock()
    session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))
    with pytest.raises(ServerDownException):
        await parser._getContent(session, "https://www.mizuho-re.co.jp/x/")


@pytest.mark.asyncio
async def test_mizuho_410_bypass_runtime_error_is_listing_ended():
    parser = MizuhoTochiParser()
    session = _session_with_status(410)
    with patch(
        "package.utils.mizuho_bypass.get_mizuho_page_html",
        new_callable=AsyncMock,
        side_effect=RuntimeError("gone"),
    ):
        with pytest.raises(ListingEndedException):
            await parser._getContent(session, "https://www.mizuho-re.co.jp/x/")


@pytest.mark.asyncio
async def test_mizuho_unexpected_http_status_raises_load_error():
    parser = MizuhoTochiParser()
    session = _session_with_status(418)
    with pytest.raises(LoadPropertyPageException):
        await parser._getContent(session, "https://www.mizuho-re.co.jp/x/")
