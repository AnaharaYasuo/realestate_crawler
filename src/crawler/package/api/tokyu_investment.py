import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_TOKYU_INVEST_START, API_KEY_TOKYU_INVEST_START_GCP, \
    API_KEY_TOKYU_INVEST_LIST, API_KEY_TOKYU_INVEST_LIST_GCP, \
    API_KEY_TOKYU_INVEST_DETAIL, API_KEY_TOKYU_INVEST_DETAIL_GCP
from package.parser.tokyuParser import TokyuInvestmentParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 2
DETAIL_PARALLEL_LIMIT = 5

class ParseTokyuInvestDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentParser("")

    def _getLocalPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""

class ParseTokyuInvestListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_LIST_GCP
        return API_KEY_TOKYU_INVEST_LIST

    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_DETAIL_GCP
        return API_KEY_TOKYU_INVEST_DETAIL

class ParseTokyuInvestStartAsync(ApiAsyncProcBase):
    urlList = ["https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/"]

    def _generateParser(self):
        return TokyuInvestmentParser("")

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_LIST_GCP
        return API_KEY_TOKYU_INVEST_LIST

    def _callApi(self):
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

# Register APIs
ApiRegistry.register(API_KEY_TOKYU_INVEST_START, ParseTokyuInvestStartAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_LIST, ParseTokyuInvestListFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_DETAIL, ParseTokyuInvestDetailFuncAsync)
