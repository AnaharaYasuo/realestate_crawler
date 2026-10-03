import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from package.api.api import ParseMiddlePageAsyncBase


class SampleMiddlePage(ParseMiddlePageAsyncBase):
    def __init__(self, pages_dict=None):
        self.pages_dict = pages_dict or {}
        self._mock_parser = MagicMock()
        self._mock_parser.getResponseBs = AsyncMock(side_effect=self._mock_get_response)
        self._mock_parser.getResponse = AsyncMock(side_effect=self._mock_get_response)
        self._mock_parser.getCharset = MagicMock(return_value="utf-8")
        super().__init__()

    async def _mock_get_response(self, session, url, charset):
        return self.pages_dict.get(url, {})

    def _getStartUrl(self):
        return "https://example.com/page1"

    def _generateParser(self):
        return self._mock_parser

    def _getApiKey(self):
        return "sample_detail"

    def _getCloudPararellLimit(self):
        return 1

    def _getLocalPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 60

    def _getParserFunc(self):
        async def _parse(res):
            for u in res.get("details", []):
                yield u
        return _parse

    def _getNextPageParserFunc(self):
        async def _next(res):
            return res.get("next_url", "")
        return _next

    def _getUrl(self):
        return "https://example.com/api/"


@pytest.mark.asyncio
async def test_middle_page_pagination_iterative_no_thread_spawn():
    """FR-CRW-012: 複数ページを巡回する際、再帰的にスレッドを生成せず同一ループ内で直列処理されること"""
    pages_data = {
        "https://example.com/page1": {
            "details": ["https://example.com/d1", "https://example.com/d2"],
            "next_url": "https://example.com/page2",
        },
        "https://example.com/page2": {
            "details": ["https://example.com/d3"],
            "next_url": "https://example.com/page3",
        },
        "https://example.com/page3": {
            "details": ["https://example.com/d4"],
            "next_url": "",
        },
    }
    obj = SampleMiddlePage(pages_data)

    initial_threads = threading.active_count()

    with patch.object(threading.Thread, "start") as mock_thread_start, \
         patch.object(obj, "_callApi", new_callable=AsyncMock) as mock_call_api:
        mock_call_api.side_effect = lambda urls: [f"done_{u}" for u in urls]
        res = await obj._run("https://example.com/page1")

        # 全詳細URLが各ページ単位で _callApi に渡されること
        assert mock_call_api.await_count == 3
        calls = [c.args[0] for c in mock_call_api.await_args_list]
        assert calls == [
            ["https://example.com/d1", "https://example.com/d2"],
            ["https://example.com/d3"],
            ["https://example.com/d4"],
        ]
        assert res == ["done_https://example.com/d1", "done_https://example.com/d2", "done_https://example.com/d3", "done_https://example.com/d4"]

        # ページネーション中に新規スレッドが一度も起動されていないこと (再帰スレッドリーク根絶)
        mock_thread_start.assert_not_called()

    # スレッドが増殖していないこと
    assert threading.active_count() <= initial_threads + 1


@pytest.mark.asyncio
async def test_middle_page_pagination_loop_guard():
    """FR-CRW-012: 次ページが同一URLまたは循環URLの場合に無限ループしないこと"""
    pages_data = {
        "https://example.com/page1": {
            "details": ["https://example.com/d1"],
            "next_url": "https://example.com/page1",  # 自己参照
        },
    }
    obj = SampleMiddlePage(pages_data)

    with patch.object(obj, "_callApi", new_callable=AsyncMock) as mock_call_api:
        mock_call_api.return_value = ["ok"]
        await obj._run("https://example.com/page1")
        assert mock_call_api.await_count == 1
