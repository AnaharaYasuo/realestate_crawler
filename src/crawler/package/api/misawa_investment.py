
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_MISAWA_INVEST_APARTMENT_START, API_KEY_MISAWA_INVEST_APARTMENT_LIST, API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, \
    API_KEY_MISAWA_INVEST_KODATE_START, API_KEY_MISAWA_INVEST_KODATE_LIST, API_KEY_MISAWA_INVEST_KODATE_DETAIL, \
    API_KEY_MISAWA_INVEST_START

from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1
DEFAULT_PARARELL_LIMIT = 1

# ==========================================
# Investment (Type 4 -> Misawa Type 4)
# ==========================================

class ParseMisawaInvestmentApartmentDetailFuncAsync(ParseDetailPageAsyncBase):
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

class ParseMisawaInvestmentApartmentListFuncAsync(ParseMiddlePageAsyncBase):
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

class ParseMisawaInvestmentKodateDetailFuncAsync(ParseDetailPageAsyncBase):
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

class ParseMisawaInvestmentKodateListFuncAsync(ParseMiddlePageAsyncBase):
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

class ParseMisawaInvestmentStartAsync(ApiAsyncProcBase):
    # Investment = Type 4 (Web ID)
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=4"]

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

class ParseMisawaInvestmentApartmentStartAsync(ParseMisawaInvestmentStartAsync):
    pass

class ParseMisawaInvestmentKodateStartAsync(ParseMisawaInvestmentStartAsync):
    def _getApiKey(self):
        return API_KEY_MISAWA_INVEST_KODATE_LIST


# ==========================================
# Registry
# ==========================================

ApiRegistry.register(API_KEY_MISAWA_INVEST_START, ParseMisawaInvestmentStartAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_APARTMENT_LIST, ParseMisawaInvestmentApartmentListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, ParseMisawaInvestmentApartmentDetailFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_KODATE_LIST, ParseMisawaInvestmentKodateListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_INVEST_KODATE_DETAIL, ParseMisawaInvestmentKodateDetailFuncAsync)
