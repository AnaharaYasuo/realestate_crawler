# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bs4 import BeautifulSoup

from package.parser.baseParser import ParserBase, RateLimitedException, ListItem
from package.parser.kenbiyaParser import KenbiyaMansionParser


class ConcreteDummyParser(ParserBase):
    property_type = "mansion"

    def createEntity(self):
        return MagicMock()

    def getCharset(self):
        return "utf-8"

    def _parseAddress(self, response, specs=None):
        return "東京都"

    def _parsePrice(self, response, specs=None):
        return 10000000

    def _parsePriceStr(self, response, specs=None):
        return "1000万円"

    def _parsePropertyName(self, response, specs=None):
        return "テスト物件"

    def _parseTransport1(self, response, specs=None):
        return "駅徒歩5分"


@pytest.mark.asyncio
async def test_parser_base_get_content_429_backoff_success():
    """ParserBase._getContent が 429 応答を受けた際、指数バックオフで待機してリトライ成功すること"""
    parser = ConcreteDummyParser()
    session = MagicMock()

    call_count = 0

    async def mock_fetch(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RateLimitedException("429 Too Many Requests")
        return b"<html>Success after 429</html>"

    with patch("package.parser.baseParser.async_fetch_html_or_data", side_effect=mock_fetch), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        content = await parser._getContent(session, "https://example.com/property")
        assert content == b"<html>Success after 429</html>"
        assert call_count == 2
        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] >= 2


@pytest.mark.asyncio
async def test_parser_base_get_content_429_max_retries_exceeded():
    """ParserBase._getContent で 429 が連続した場合、最大試行回数後に RateLimitedException を送出すること"""
    parser = ConcreteDummyParser()
    session = MagicMock()

    with patch("package.parser.baseParser.async_fetch_html_or_data", side_effect=RateLimitedException("429")), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(RateLimitedException):
            await parser._getContent(session, "https://example.com/property")
        assert mock_sleep.call_count >= 1


@pytest.mark.asyncio
async def test_kenbiya_card_price_extraction():
    """Kenbiya の一覧ページで、テーブル形式やカード形式から正しく価格が抽出され ListItem に設定されること"""
    parser = KenbiyaMansionParser()

    html = """
    <html>
      <body>
        <div class="bf-box">
          <div class="bf-tit"><a href="/pp1/s/tokyo/adachi-ku/re_11111/">物件1</a></div>
          <div class="bf-info">
            <dl>
              <dt>価格</dt>
              <dd class="price">1,980万円</dd>
            </dl>
          </div>
        </div>
        <tr>
          <td><a href="/pp1/s/tokyo/adachi-ku/re_22222/">物件2</a></td>
          <td class="price">3,450万円</td>
        </tr>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]

    assert len(items) == 2
    assert items[0].url == "https://www.kenbiya.com/pp1/s/tokyo/adachi-ku/re_11111/"
    assert items[0].price == 19800000

    assert items[1].url == "https://www.kenbiya.com/pp1/s/tokyo/adachi-ku/re_22222/"
    assert items[1].price == 34500000
