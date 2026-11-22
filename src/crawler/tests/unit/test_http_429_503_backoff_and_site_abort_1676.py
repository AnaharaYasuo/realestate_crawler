import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from package.api.api import (
    ApiAsyncProcBase,
    ParseDetailPageAsyncBase,
    SiteCrawlAbortedException,
)
from package.parser.baseParser import (
    ParserBase,
    RateLimitedException,
    ServerBusyException,
    ServiceUnavailableException,
)


class _DummyParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return {}

    def _parsePropertyName(self, soup):
        return ""

    def _parsePriceStr(self, soup):
        return ""

    def _parsePrice(self, soup):
        return None

    def _parseAddress(self, soup):
        return ""

    def _parseTransport1(self, soup):
        return ""

    async def parseRootPage(self, response):
        return []

    async def parseMiddlePage(self, response):
        return []

    async def parsePropertyDetailPage(self, response):
        return None


class _DummyDetailProcBase(ParseDetailPageAsyncBase):
    def _getApiKey(self):
        return "dummy"

    def _getCloudPararellLimit(self):
        return 1

    def _getLocalPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _generateParser(self):
        return _DummyParser()


@pytest.mark.asyncio
async def test_get_content_503_retries_with_exponential_backoff_and_recovers():
    parser = _DummyParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 3

    calls = 0

    async def fake_fetch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ServiceUnavailableException("HTTP Status 503 Service Unavailable: https://example.com/1")
        return b"<html>ok</html>"

    sleep_delays = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    with (
        patch("package.parser.baseParser.async_fetch_html_or_data", side_effect=fake_fetch),
        patch("package.parser.baseParser.asyncio.sleep", side_effect=fake_sleep),
    ):
        result = await parser._getContent(MagicMock(), "https://example.com/1")

    assert result == b"<html>ok</html>"
    assert calls == 3
    assert sleep_delays == [2, 4]


@pytest.mark.asyncio
async def test_get_content_503_exhausted_logs_error_and_raises(caplog):
    parser = _DummyParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 3

    async def fake_fetch(*args, **kwargs):
        raise ServiceUnavailableException("HTTP Status 503 Service Unavailable: https://example.com/1")

    with (
        patch("package.parser.baseParser.async_fetch_html_or_data", side_effect=fake_fetch),
        patch("package.parser.baseParser.asyncio.sleep", new=AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        with pytest.raises(ServiceUnavailableException):
            await parser._getContent(MagicMock(), "https://example.com/1")

    assert any("503" in rec.message for rec in caplog.records if rec.levelno >= logging.ERROR)


@pytest.mark.asyncio
async def test_get_content_429_exhausted_logs_error_and_raises(caplog):
    parser = _DummyParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 2

    async def fake_fetch(*args, **kwargs):
        raise RateLimitedException("HTTP Status 429 Too Many Requests: https://example.com/1")

    with (
        patch("package.parser.baseParser.async_fetch_html_or_data", side_effect=fake_fetch),
        patch("package.parser.baseParser.asyncio.sleep", new=AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        with pytest.raises(RateLimitedException):
            await parser._getContent(MagicMock(), "https://example.com/1")

    assert any("429" in rec.message for rec in caplog.records if rec.levelno >= logging.ERROR)


@pytest.mark.asyncio
async def test_validate_http_status_503_raises_service_unavailable():
    with pytest.raises(ServiceUnavailableException):
        ParserBase._validate_http_status(503, "https://example.com/503")
    assert issubclass(ServiceUnavailableException, ServerBusyException)


@pytest.mark.asyncio
async def test_site_abort_stops_subsequent_tasks_for_same_site_only():
    ApiAsyncProcBase.clear_aborted_sites()

    class _SiteAProc(_DummyDetailProcBase):
        def _getTreatPageArg(self):
            return "https://site-a.example.com/detail/1"

        async def _treatPage(self, session, arg):
            raise RateLimitedException("429 exhausted")

    class _SiteASecondProc(_DummyDetailProcBase):
        called = False

        def _getTreatPageArg(self):
            return "https://site-a.example.com/detail/2"

        async def _treatPage(self, session, arg):
            _SiteASecondProc.called = True
            return "should_not_run"

    class _SiteBProc(_DummyDetailProcBase):
        def _getTreatPageArg(self):
            return "https://site-b.example.com/detail/1"

        async def _treatPage(self, session, arg):
            return "ok_b"

    proc_a1 = _SiteAProc()
    with patch.object(proc_a1, "_resolve_target_company", return_value="site_a"):
        with pytest.raises(SiteCrawlAbortedException):
            await proc_a1._run("https://site-a.example.com/detail/1")

    proc_a2 = _SiteASecondProc()
    with patch.object(proc_a2, "_resolve_target_company", return_value="site_a"):
        with pytest.raises(SiteCrawlAbortedException):
            await proc_a2._run("https://site-a.example.com/detail/2")
    assert _SiteASecondProc.called is False

    proc_b = _SiteBProc()
    with patch.object(proc_b, "_resolve_target_company", return_value="site_b"):
        res_b = await proc_b._run("https://site-b.example.com/detail/1")
    assert res_b == "ok_b"

    ApiAsyncProcBase.clear_aborted_sites()



def test_classify_fetch_exception_handles_server_busy_and_skip_without_name_error():
    from types import SimpleNamespace
    from package.api.api import ParseDetailPageAsyncBase, _server_busy_abort_event
    from package.parser.baseParser import ServerBusyException, SkipPropertyException

    dummy = SimpleNamespace(url="https://example.com/detail/1", _get_cooldown_config=lambda: None)

    try:
        assert ParseDetailPageAsyncBase._classify_fetch_exception(dummy, SkipPropertyException("skip")) == (None, False, None)
        assert ParseDetailPageAsyncBase._classify_fetch_exception(dummy, ServerBusyException("busy")) == (None, False, None)
    finally:
        _server_busy_abort_event.clear()
