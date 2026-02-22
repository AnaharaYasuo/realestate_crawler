
import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_SUMIFU_INVEST_KODATE_START, API_KEY_SUMIFU_INVEST_KODATE_LIST, API_KEY_SUMIFU_INVEST_KODATE_DETAIL, \
    API_KEY_SUMIFU_INVEST_KODATE_START_GCP, API_KEY_SUMIFU_INVEST_KODATE_LIST_GCP, API_KEY_SUMIFU_INVEST_KODATE_DETAIL_GCP, \
    API_KEY_SUMIFU_INVEST_APARTMENT_START, API_KEY_SUMIFU_INVEST_APARTMENT_LIST, API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL, \
    API_KEY_SUMIFU_INVEST_APARTMENT_START_GCP, API_KEY_SUMIFU_INVEST_APARTMENT_LIST_GCP, API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL_GCP

from package.parser.sumifuParser import SumifuInvestmentKodateParser, SumifuInvestmentApartmentParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 2
DETAIL_PARALLEL_LIMIT = 5

# ==============================================================================
#  BASE CLASSES
# ==============================================================================

class ParseSumifuInvestDetailFuncAsyncBase(ParseDetailPageAsyncBase):
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

class ParseSumifuInvestListFuncAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage
    
    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _isBsMiddlePage(self):
        return True

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 360

class ParseSumifuInvestStartAsyncBase(ApiAsyncProcBase):
    # Default placeholder URL
    urlList = ["https://www.stepon.co.jp/pro/ca_0_001/?smk=111111111110&limit=1000"]

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 2400

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

# ==============================================================================
#  KODATE (戸建て賃貸)
# ==============================================================================

class ParseSumifuInvestKodateDetailFuncAsync(ParseSumifuInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentKodateParser("")

class ParseSumifuInvestKodateListFuncAsync(ParseSumifuInvestListFuncAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentKodateParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_KODATE_LIST_GCP
        return API_KEY_SUMIFU_INVEST_KODATE_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_KODATE_DETAIL_GCP
        return API_KEY_SUMIFU_INVEST_KODATE_DETAIL

class ParseSumifuInvestKodateStartAsync(ParseSumifuInvestStartAsyncBase):
    # 戸建 (7桁目が1)
    urlList = ["https://www.stepon.co.jp/pro/ca_0_001/?smk=000000100000&limit=1000"]

    def _generateParser(self):
        return SumifuInvestmentKodateParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_KODATE_LIST_GCP
        return API_KEY_SUMIFU_INVEST_KODATE_LIST

# ==============================================================================
#  APARTMENT (アパート)
# ==============================================================================

class ParseSumifuInvestApartmentDetailFuncAsync(ParseSumifuInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentApartmentParser("")

class ParseSumifuInvestApartmentListFuncAsync(ParseSumifuInvestListFuncAsyncBase):
    def _generateParser(self):
        return SumifuInvestmentApartmentParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_APARTMENT_LIST_GCP
        return API_KEY_SUMIFU_INVEST_APARTMENT_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL_GCP
        return API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL

class ParseSumifuInvestApartmentStartAsync(ParseSumifuInvestStartAsyncBase):
    # アパート (2桁目が1)
    urlList = ["https://www.stepon.co.jp/pro/ca_0_001/?smk=010000000000&limit=1000"]

    def _generateParser(self):
        return SumifuInvestmentApartmentParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_INVEST_APARTMENT_LIST_GCP
        return API_KEY_SUMIFU_INVEST_APARTMENT_LIST


# ==============================================================================
#  REGISTRY
# ==============================================================================

# Kodate
ApiRegistry.register(API_KEY_SUMIFU_INVEST_KODATE_START, ParseSumifuInvestKodateStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_KODATE_LIST, ParseSumifuInvestKodateListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_KODATE_DETAIL, ParseSumifuInvestKodateDetailFuncAsync)

# Apartment
ApiRegistry.register(API_KEY_SUMIFU_INVEST_APARTMENT_START, ParseSumifuInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_APARTMENT_LIST, ParseSumifuInvestApartmentListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL, ParseSumifuInvestApartmentDetailFuncAsync)
