
import asyncio
import ssl
import aiohttp
from package.api.api import (
    ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase,
    TCP_CONNECTOR_LIMIT,
    API_KEY_MISAWA_INVEST_APARTMENT_LIST, API_KEY_MISAWA_INVEST_APARTMENT_DETAIL,
    API_KEY_MISAWA_INVEST_KODATE_LIST, API_KEY_MISAWA_INVEST_KODATE_DETAIL,
    API_KEY_MISAWA_INVEST_START
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 3
DEFAULT_PARARELL_LIMIT = 1


class MisawaInvestmentConnectorMixin:
    """Provides legacy TLS compatibility for Misawa's legacy servers."""
    def _generateConnector(self, _loop):  # NOSONAR
        ctx = ssl.create_default_context()
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')  # NOSONAR
        except Exception:
            pass
        return aiohttp.TCPConnector(loop=_loop, limit=TCP_CONNECTOR_LIMIT, ssl=ctx)


# ==========================================
# Investment (Type 4 -> Misawa Type 4)
# ==========================================

class ParseMisawaInvestmentApartmentDetailFuncAsync(MisawaInvestmentConnectorMixin, ParseDetailPageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentApartmentParser
        return MisawaInvestmentApartmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMisawaInvestmentApartmentListFuncAsync(MisawaInvestmentConnectorMixin, ParseMiddlePageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentApartmentParser
        return MisawaInvestmentApartmentParser()

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage

    def _isBsMiddlePage(self):
        return True

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        return API_KEY_MISAWA_INVEST_APARTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MISAWA_INVEST_APARTMENT_LIST

class ParseMisawaInvestmentKodateDetailFuncAsync(MisawaInvestmentConnectorMixin, ParseDetailPageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentKodateParser
        return MisawaInvestmentKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMisawaInvestmentKodateListFuncAsync(MisawaInvestmentConnectorMixin, ParseMiddlePageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentKodateParser
        return MisawaInvestmentKodateParser()

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage

    def _isBsMiddlePage(self):
        return True

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        return API_KEY_MISAWA_INVEST_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MISAWA_INVEST_KODATE_LIST

class ParseMisawaInvestmentStartAsync(MisawaInvestmentConnectorMixin, ApiAsyncProcBase):
    # Investment = Type 9 (Web ID)
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=9"]

    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentApartmentParser
        return MisawaInvestmentApartmentParser()

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return API_KEY_MISAWA_INVEST_APARTMENT_LIST 

    async def _callApi(self, urlList):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses

    def _getTreatPageArg(self):
        return

class ParseMisawaInvestmentKodateStartAsync(ParseMisawaInvestmentStartAsync):
    # Invest inventory is type=9 (shared list). Rows include アパート/一棟/戸建貸家;
    # MisawaInvestmentKodateParser skips non-戸建. Explicit urlList so catalog seed
    # is not ambiguous with the apartment Start class.
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=9"]

    def _generateParser(self):
        from package.parser.misawaParser import MisawaInvestmentKodateParser
        return MisawaInvestmentKodateParser()

    def _getApiKey(self):
        return API_KEY_MISAWA_INVEST_KODATE_LIST


class ParseMisawaInvestmentApartmentStartAsync(ParseMisawaInvestmentStartAsync):
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=9"]


# Import missing constants
from package.api.api import API_KEY_MISAWA_INVEST_KODATE_START, API_KEY_MISAWA_INVEST_APARTMENT_START

# ==========================================
# Registry
# ==========================================

ApiRegistry.register(API_KEY_MISAWA_INVEST_START, ParseMisawaInvestmentStartAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_KODATE_START, ParseMisawaInvestmentKodateStartAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_APARTMENT_START, ParseMisawaInvestmentApartmentStartAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_APARTMENT_LIST, ParseMisawaInvestmentApartmentListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, ParseMisawaInvestmentApartmentDetailFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_KODATE_LIST, ParseMisawaInvestmentKodateListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_KODATE_DETAIL, ParseMisawaInvestmentKodateDetailFuncAsync)

