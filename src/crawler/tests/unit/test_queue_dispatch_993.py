import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from package.api.api import ParseMiddlePageAsyncBase, DEFAULT_DISPATCH_QUEUE_SIZE
from package.api.sumifu_investment import ParseSumifuInvestStartAsyncBase


class DummyMiddlePage(ParseMiddlePageAsyncBase):
    def __init__(self, pages_dict=None):
        self.pages_dict = pages_dict or {}
        self._mock_parser = MagicMock()
        self._mock_parser.getResponseBs = AsyncMock(side_effect=self._mock_get_response)
        self._mock_parser.getResponse = AsyncMock(side_effect=self._mock_get_response)
        self._mock_parser.getCharset = MagicMock(return_value="utf-8")
        super().__init__()

    async def _mock_get_response(self, session, url, charset):
        return self.pages_dict.get(url, {})

    def _generateParser(self):
        return self._mock_parser

    def _getApiKey(self):
        return "/api/dummy/detail"

    def _getCloudPararellLimit(self):
        return 2

    def _getLocalPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 60

    def _getParserFunc(self):
        async def _parse(res):
            for u in res.get("details", []):
                yield u
        return _parse

    def _getNextPageParserFunc(self):
        async def _next(res, current_url=None):
            return res.get("next_url", "")
        return _next

    def _getUrl(self):
        return "https://example.com"


@pytest.mark.asyncio
async def test_queue_dispatch_default_size():
    """CRAWLER_DISPATCH_QUEUE_SIZE defaults to 5000"""
    assert DEFAULT_DISPATCH_QUEUE_SIZE == 5000


@pytest.mark.asyncio
async def test_queue_dispatch_execution_and_worker_drain():
    """Middle page puts details into queue and workers drain all items concurrently"""
    pages_data = {
        "https://example.com/list1": {
            "details": ["https://example.com/d1", "https://example.com/d2"],
            "next_url": "https://example.com/list2",
        },
        "https://example.com/list2": {
            "details": ["https://example.com/d3"],
            "next_url": "",
        },
    }
    crawler = DummyMiddlePage(pages_data)

    dispatched = []

    async def mock_fetch_with_session(detail_url, api_url, loop):
        await asyncio.sleep(0.01)
        dispatched.append(detail_url)
        return detail_url, 200, "OK"

    with patch.object(crawler, "_fetchWithEachSession", side_effect=mock_fetch_with_session):
        res = await crawler._run("https://example.com/list1")

    assert len(dispatched) == 3
    assert set(dispatched) == {"https://example.com/d1", "https://example.com/d2", "https://example.com/d3"}
    assert len(res) == 3


@pytest.mark.asyncio
async def test_sumifu_get_area_dest_url_no_limit_1000():
    """Sumifu parser getAreaDestUrl does not append limit=1000"""
    from package.parser.sumifuParser import SumifuKodateParser
    parser = SumifuKodateParser()
    link = "/kodate/area_tokyo/shinjuku/"
    dest = parser.getAreaDestUrl(link)
    assert "limit=1000" not in dest
    assert dest == "https://www.stepon.co.jp/kodate/area_tokyo/shinjuku/"


def test_sumifu_investment_start_no_limit_1000():
    """Sumifu investment start URL does not contain limit=1000"""
    urls = ParseSumifuInvestStartAsyncBase.urlList
    for u in urls:
        assert "limit=1000" not in u
