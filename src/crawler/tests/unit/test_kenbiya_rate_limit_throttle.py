import os
import time
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from package.api.api import ParseDetailPageAsyncBase
from package.api.adaptive_concurrency import AdaptiveConcurrencyController
from package.parser.kenbiyaParser import KenbiyaParserBase


def test_kenbiya_site_download_delays():
    """ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS に kenbiya が2.0秒以上で登録されていること"""
    assert "kenbiya" in ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS
    assert ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS["kenbiya"] >= 2.0


def test_kenbiya_concurrency_cap():
    """AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS に kenbiya が1で登録されていること"""
    assert "kenbiya" in AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS
    assert AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS["kenbiya"] == 1


@pytest.mark.asyncio
async def test_kenbiya_throttle_before_request_default_enabled(monkeypatch):
    """環境変数なし（ローカル環境）でも _throttle_before_request がスロットルを実行すること"""
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)
    monkeypatch.delenv("KENBIYA_THROTTLE", raising=False)
    monkeypatch.delenv("KENBIYA_THROTTLE_DISABLED", raising=False)
    monkeypatch.setenv("KENBIYA_MIN_INTERVAL", "0.2")

    # Reset last request time
    KenbiyaParserBase._last_request_time = time.monotonic()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await KenbiyaParserBase._throttle_before_request()
        # sleep should have been called because elapsed < min_interval
        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] > 0


@pytest.mark.asyncio
async def test_kenbiya_throttle_disabled_via_env(monkeypatch):
    """KENBIYA_THROTTLE_DISABLED=true の場合はスロットルをスキップすること"""
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "true")
    monkeypatch.setenv("KENBIYA_MIN_INTERVAL", "1.0")

    KenbiyaParserBase._last_request_time = time.monotonic()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await KenbiyaParserBase._throttle_before_request()
        assert not mock_sleep.called


@pytest.mark.asyncio
async def test_kenbiya_handle_curl_cffi_response_200():
    from package.parser.kenbiyaParser import KenbiyaMansionParser

    parser = KenbiyaMansionParser()
    res = await parser._handle_curl_cffi_response(200, b"<html>ok</html>", "https://www.kenbiya.com/test", 0, 3)
    assert res == b"<html>ok</html>"


@pytest.mark.asyncio
async def test_kenbiya_handle_curl_cffi_response_404_and_429():
    from unittest.mock import AsyncMock, patch
    from package.parser.kenbiyaParser import KenbiyaMansionParser
    from package.parser.baseParser import ListingEndedException, LoadPropertyPageException

    parser = KenbiyaMansionParser()
    with pytest.raises(ListingEndedException):
        await parser._handle_curl_cffi_response(404, b"", "https://www.kenbiya.com/test", 0, 3)

    with patch.object(parser, "_sleep_backoff", new=AsyncMock()) as mock_sleep:
        res = await parser._handle_curl_cffi_response(429, b"", "https://www.kenbiya.com/test", 0, 3)
        assert res is None
        mock_sleep.assert_awaited_once()

    with pytest.raises(LoadPropertyPageException):
        await parser._handle_curl_cffi_response(500, b"", "https://www.kenbiya.com/test", 0, 3)
