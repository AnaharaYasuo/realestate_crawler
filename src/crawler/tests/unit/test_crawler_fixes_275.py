import pytest
from bs4 import BeautifulSoup

from scripts.ops.run_all_crawlers import format_duration
from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser, MitsuiTochiParser, MitsuiInvestmentParser
from package.parser.tokyuParser import TokyuTochiParser
from package.parser.keioParser import KeioMansionParser
from package.parser.afrParser import AfrMansionParser
from package.parser.baseParser import SkipPropertyException
from package.api.misawa_investment import ParseMisawaInvestmentStartAsync


def test_format_duration():
    assert format_duration(45) == "45秒"
    assert format_duration(192) == "3分12秒"
    assert format_duration(3600) == "1時間0分0秒"
    assert format_duration(8130) == "2時間15分30秒"


def test_mitsui_root_xpath_and_dest_url():
    p_mansion = MitsuiMansionParser()
    p_kodate = MitsuiKodateParser()
    p_tochi = MitsuiTochiParser()
    p_invest = MitsuiInvestmentParser()

    assert "prefecture/" in p_mansion.getRootXpath()
    assert "not(contains(@href,'/store/'))" in p_mansion.getRootXpath()

    # Relative URL resolution
    assert p_mansion.getRootDestUrl("prefecture/13/") == "https://www.rehouse.co.jp/buy/mansion/prefecture/13/"
    assert p_kodate.getRootDestUrl("prefecture/14/") == "https://www.rehouse.co.jp/buy/kodate/prefecture/14/"
    assert p_tochi.getRootDestUrl("prefecture/11/") == "https://www.rehouse.co.jp/buy/tochi/prefecture/11/"
    assert p_invest.getRootDestUrl("prefecture/13/") == "https://www.rehouse.co.jp/buy/tohshi/prefecture/13/"


def test_tokyu_tochi_parser():
    p = TokyuTochiParser()
    xpath = p.getRootXpath()
    assert "/kounyu/tochi/" in xpath
    assert "/select-area" in xpath


def test_misawa_investment_type():
    obj = ParseMisawaInvestmentStartAsync()
    assert len(obj.urlList) > 0
    assert "bukken_type[]=9" in obj.urlList[0]
    assert "bukken_type[]=4" not in obj.urlList[0]


def test_afr_mansion_guard():
    p = AfrMansionParser()
    # HTML without 専有面積 should raise SkipPropertyException
    html = "<html><body><table><tr><th>建物面積</th><td>100m2</td></tr><tr><th>土地面積</th><td>150m2</td></tr></table></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    entity = p.createEntity()
    with pytest.raises(SkipPropertyException):
        p._parsePropertyDetailPage(entity, soup)


def test_afr_mansion_wall_core_area():
    p = AfrMansionParser()
    # HTML with 壁芯面積 should succeed without SkipPropertyException
    html = "<html><body><table><tr><th>壁芯面積</th><td>65.4m2</td></tr></table></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    entity = p.createEntity()
    res = p._parsePropertyDetailPage(entity, soup)
    assert res.senyuMensekiStr == "65.4m2"


def test_keio_parser_abs_links():
    p = KeioMansionParser()
    html = '''<html><body>
        <a class="abs_link" href="/sale/2127977638870000006489/">Detail</a>
        <a class="abs_link" href="/sale/other/not_id/">Other</a>
    </body></html>'''
    soup = BeautifulSoup(html, "html.parser")
    import asyncio
    async def run():
        return [u async for u in p.parseRootPage(soup)]
    urls = asyncio.run(run())
    assert len(urls) == 1
    assert "2127977638870000006489" in urls[0]


def test_misawa_investment_connector():
    import asyncio
    obj = ParseMisawaInvestmentStartAsync()
    loop = asyncio.new_event_loop()
    try:
        connector = obj._generateConnector(loop)
        assert connector is not None
        assert connector._ssl is not None
    finally:
        loop.close()


def test_keio_parser_get_response_bs():
    from unittest.mock import patch, MagicMock
    p = KeioMansionParser()
    import asyncio

    # Success case with JSON html
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"html": "<p>Hello Keio</p>"}
    with patch("package.parser.keioParser.requests.get", return_value=mock_resp):
        soup = asyncio.run(p.getResponseBs(None, "https://chukai.keiofudosan.co.jp/sale/search/get_search_result_sale/123", "utf-8"))
        assert "Hello Keio" in soup.text

    # Exception case returns empty soup
    with patch("package.parser.keioParser.requests.get", side_effect=RuntimeError("network error")):
        soup_err = asyncio.run(p.getResponseBs(None, "https://chukai.keiofudosan.co.jp/sale/search/get_search_result_sale/123", "utf-8"))
        assert soup_err.text == ""


def test_base_parser_xpath_starts_with_and_not_contains():
    import asyncio
    p = MitsuiMansionParser()
    # Test _parsePageCore logic with starts-with and not(contains)
    xpath = "//a[starts-with(@href, 'https://www.rehouse.co.jp/buy/') and not(contains(@href, '/store/')) and contains(@href, 'mansion')]"
    html = '''<html><body>
        <a href="https://www.rehouse.co.jp/buy/mansion/tokyo/">Tokyo</a>
        <a href="https://www.rehouse.co.jp/buy/mansion/store/123/">Store</a>
        <a href="https://www.rehouse.co.jp/rent/mansion/tokyo/">Rent</a>
    </body></html>'''
    soup = BeautifulSoup(html, "html.parser")
    async def run():
        return [u async for u in p._parsePageCore(soup, xpath_fn=lambda: xpath, dest_url_fn=lambda h: h)]
    urls = asyncio.run(run())
    assert len(urls) == 1
    assert "/buy/mansion/tokyo/" in urls[0]




def test_api_middle_page_next_page_fetch():
    from unittest.mock import AsyncMock, patch
    from package.api.api import ParseMiddlePageAsyncBase
    import asyncio

    class DummyMiddlePage(ParseMiddlePageAsyncBase):
        def _getStartUrl(self):
            return "http://test.example.com"
        def _generateParser(self):
            return None
        def _getApiKey(self):
            return "dummy"
        def _getCloudPararellLimit(self):
            return 1
        def _getLocalPararellLimit(self):
            return 1
        def _getTimeOutSecond(self):
            return 10
        def _getParserFunc(self):
            async def _dummy(res):
                if False:
                    yield None
            return _dummy
        def _getNextPageParserFunc(self):
            async def _next(res):
                return "http://test.example.com/next"
            return _next
        def _getUrl(self):
            return "http://api.example.com"

    obj = DummyMiddlePage()
    from unittest.mock import MagicMock
    obj.parser = MagicMock()
    obj.url = "http://test.example.com"
    obj.parser.getResponse = AsyncMock(return_value="<html></html>")
    obj.parser.getCharset = MagicMock(return_value="utf-8")

    async def run():
        with patch.object(obj, "_fetch", new_callable=AsyncMock) as mock_fetch:
            urls = await obj._treatPage(None)
            assert isinstance(urls, list)
            mock_fetch.assert_awaited()

    asyncio.run(run())




