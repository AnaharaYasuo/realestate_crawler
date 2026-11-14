# -*- coding: utf-8 -*-
"""
共通HTTPクライアント (package.utils.http_client) の単体テスト
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch

from package.utils.http_client import (
    async_fetch_html_or_data,
    fetch_image_bytes,
    FastAbortNonHtmlException,
    MaxPayloadExceededException,
    DEFAULT_HEADERS,
    ALLOWED_CONTENT_TYPES,
)


@pytest.mark.asyncio
async def test_async_fetch_html_success():
    """正常なHTMLレスポンスが正しく取得できること"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.read.return_value = b"<html><body>OK</body></html>"
    mock_session.get.return_value.__aenter__.return_value = mock_response

    data = await async_fetch_html_or_data(mock_session, "https://example.com/property/1")
    assert data == b"<html><body>OK</body></html>"

    # デフォルトヘッダーが引き渡されていること
    call_kwargs = mock_session.get.call_args[1]
    headers = call_kwargs["headers"]
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "text/html" in headers["Accept"]


@pytest.mark.asyncio
async def test_async_fetch_json_success():
    """正常なJSONレスポンスが正しく取得できること"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json; charset=utf-8"}
    mock_response.read.return_value = b'{"status": "ok"}'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    data = await async_fetch_html_or_data(mock_session, "https://example.com/api/v1")
    assert data == b'{"status": "ok"}'


@pytest.mark.asyncio
async def test_async_fetch_fast_abort_pdf():
    """PDFなどの非HTML・非データリソースを受信時、即座にAbortして例外または空レスポンスとなること"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.read = AsyncMock()  # 本文readが呼ばれてはならない
    mock_response.close = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(FastAbortNonHtmlException) as exc_info:
        await async_fetch_html_or_data(
            mock_session, "https://example.com/flyer.pdf", raise_on_non_html=True
        )
    assert "application/pdf" in str(exc_info.value)
    # 本文readが呼ばれていないこと（即時切断）
    mock_response.read.assert_not_called()
    mock_response.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_fast_abort_silent():
    """raise_on_non_html=False の場合、例外を投げずに空bytesを返すこと"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "video/mp4"}
    mock_response.read = AsyncMock()
    mock_response.close = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    data = await async_fetch_html_or_data(
        mock_session, "https://example.com/video.mp4", raise_on_non_html=False
    )
    assert data == b""
    mock_response.read.assert_not_called()
    mock_response.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_max_payload_exceeded():
    """Content-Lengthが最大許容サイズ（デフォルト10MB）を超えている場合即時Abortすること"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {
        "Content-Type": "text/html",
        "Content-Length": "15000000",  # 15MB
    }
    mock_response.content_length = 15000000
    mock_response.read = AsyncMock()
    mock_response.close = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(MaxPayloadExceededException):
        await async_fetch_html_or_data(
            mock_session, "https://example.com/huge.html", max_bytes=10_000_000
        )
    mock_response.read.assert_not_called()
    mock_response.close.assert_called_once()


def test_fetch_image_bytes_oversize():
    """画像取得時、Content-Lengthが上限（5MB）を超える場合は取得をスキップすること"""
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "image/jpeg", "Content-Length": "8000000"}  # 8MB
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        img_bytes = fetch_image_bytes("https://example.com/huge.jpg", max_bytes=5_000_000)
        assert img_bytes is None


def test_fetch_image_bytes_non_image():
    """画像取得時、Content-Typeが画像でない場合はスキップすること"""
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        img_bytes = fetch_image_bytes("https://example.com/not_image.html")
        assert img_bytes is None


def test_fetch_image_bytes_success():
    """正常な画像取得"""
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "image/png", "Content-Length": "12345"}
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"\x89PNG\r\n\x1a\nfakeimagebytes"]

    with patch("requests.get", return_value=mock_resp):
        img_bytes = fetch_image_bytes("https://example.com/pic.png")
        assert img_bytes == b"\x89PNG\r\n\x1a\nfakeimagebytes"
