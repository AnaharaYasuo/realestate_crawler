# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, patch
import pytest
from bs4 import BeautifulSoup
from package.api.api import ParseMiddlePageAsyncBase


class DummyMiddlePageForTest(ParseMiddlePageAsyncBase):
    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _generateParser(self):
        return None

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return "detail"

    def _getTreatPageArg(self):
        return None

    def _getParserFunc(self):
        async def empty_generator(_response):
            if False:  # noqa: B018
                yield "never"
        return empty_generator


@pytest.mark.asyncio
async def test_process_middle_page_stream_zero_items_triggers_error_html_save():
    """中間ページストリーミングで抽出アイテムが0件の場合に_save_error_html_by_urlが呼び出されること (Issue #1310)"""
    instance = DummyMiddlePageForTest()
    instance._callApi = AsyncMock(return_value=[])
    instance._extract_next_page_url = AsyncMock(return_value="")

    with patch.object(instance, "_save_error_html_by_url", new_callable=AsyncMock) as mock_save:
        html = "<html><body><ul id='result_list'></ul></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        results = []
        next_url = await instance._process_middle_page_stream(soup, "https://example.com/list/page1", results)

        assert next_url == ""
        assert len(results) == 0
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0]
        assert call_args[0] == "https://example.com/list/page1"
        assert "Zero items parsed from middle page" in call_args[2]
