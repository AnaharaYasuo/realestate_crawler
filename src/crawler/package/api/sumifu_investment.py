import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_SUMIFU_INVEST_START, API_KEY_SUMIFU_INVEST_START_GCP, \
    API_KEY_SUMIFU_INVEST_LIST, API_KEY_SUMIFU_INVEST_LIST_GCP, \
    API_KEY_SUMIFU_INVEST_DETAIL, API_KEY_SUMIFU_INVEST_DETAIL_GCP
from package.parser.sumifuParser import SumifuInvestmentParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 2
DETAIL_PARALLEL_LIMIT = 5

class ParseSumifuInvestDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentParser("")

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

class ParseSumifuInvestListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_LIST_GCP
        return API_KEY_SUMIFU_INVEST_LIST

    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_DETAIL_GCP
        return API_KEY_SUMIFU_INVEST_DETAIL

class ParseSumifuInvestStartAsync(ApiAsyncProcBase):
    # National level search with All Buildings bitmask
    urlList = ["https://www.stepon.co.jp/pro/ca_0_001/?smk=111111111110&limit=1000"]

    def _generateParser(self):
        return SumifuInvestmentParser("")

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_LIST_GCP
        return API_KEY_SUMIFU_INVEST_LIST

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
ApiRegistry.register(API_KEY_SUMIFU_INVEST_START, ParseSumifuInvestStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_LIST, ParseSumifuInvestListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_DETAIL, ParseSumifuInvestDetailFuncAsync)
