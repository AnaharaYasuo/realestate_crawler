
import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_TOKYU_INVEST_APARTMENT_START, API_KEY_TOKYU_INVEST_APARTMENT_LIST, API_KEY_TOKYU_INVEST_APARTMENT_DETAIL, \
    API_KEY_TOKYU_INVEST_APARTMENT_START_GCP, API_KEY_TOKYU_INVEST_APARTMENT_LIST_GCP, API_KEY_TOKYU_INVEST_APARTMENT_DETAIL_GCP, \
    API_KEY_TOKYU_INVEST_KODATE_START, API_KEY_TOKYU_INVEST_KODATE_LIST, API_KEY_TOKYU_INVEST_KODATE_DETAIL, \
    API_KEY_TOKYU_INVEST_KODATE_START_GCP, API_KEY_TOKYU_INVEST_KODATE_LIST_GCP, API_KEY_TOKYU_INVEST_KODATE_DETAIL_GCP

from package.parser.tokyuParser import TokyuInvestmentApartmentParser, TokyuInvestmentParser, TokyuInvestmentKodateParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 1
DETAIL_PARALLEL_LIMIT = 1

# ==============================================================================
#  BASE CLASSES
# ==============================================================================

class ParseTokyuInvestDetailFuncAsyncBase(ParseDetailPageAsyncBase):
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

class ParseTokyuInvestListFuncAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage
    
    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _isBsMiddlePage(self):
        return True

class ParseTokyuInvestStartAsyncBase(ApiAsyncProcBase):
    urlList = ["https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/"]

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
#  APARTMENT (アパート)
# ==============================================================================

class ParseTokyuInvestApartmentDetailFuncAsync(ParseTokyuInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentApartmentParser("")

class ParseTokyuInvestApartmentListFuncAsync(ParseTokyuInvestListFuncAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentApartmentParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_APARTMENT_LIST_GCP
        return API_KEY_TOKYU_INVEST_APARTMENT_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_APARTMENT_DETAIL_GCP
        return API_KEY_TOKYU_INVEST_APARTMENT_DETAIL

class ParseTokyuInvestApartmentStartAsync(ParseTokyuInvestStartAsyncBase):
    urlList = ["https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=apart/"]

    def _generateParser(self):
        return TokyuInvestmentApartmentParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_APARTMENT_LIST_GCP
        return API_KEY_TOKYU_INVEST_APARTMENT_LIST

# ==============================================================================
#  REGISTRY
# ==============================================================================

# Apartment
ApiRegistry.register(API_KEY_TOKYU_INVEST_APARTMENT_START, ParseTokyuInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_APARTMENT_LIST, ParseTokyuInvestApartmentListFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_APARTMENT_DETAIL, ParseTokyuInvestApartmentDetailFuncAsync)


# ==============================================================================
#  KODATE (戸建て賃貸)
# ==============================================================================

class ParseTokyuInvestKodateDetailFuncAsync(ParseTokyuInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentKodateParser("")

class ParseTokyuInvestKodateListFuncAsync(ParseTokyuInvestListFuncAsyncBase):
    def _generateParser(self):
        return TokyuInvestmentKodateParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_KODATE_LIST_GCP
        return API_KEY_TOKYU_INVEST_KODATE_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_KODATE_DETAIL_GCP
        return API_KEY_TOKYU_INVEST_KODATE_DETAIL

class ParseTokyuInvestKodateStartAsync(ParseTokyuInvestStartAsyncBase):
    # Verified URL pattern for Kodate/Houses
    urlList = ["https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=kodate/"] 

    def _generateParser(self):
        return TokyuInvestmentKodateParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_INVEST_KODATE_LIST_GCP
        return API_KEY_TOKYU_INVEST_KODATE_LIST

# Kodate
ApiRegistry.register(API_KEY_TOKYU_INVEST_KODATE_START, ParseTokyuInvestKodateStartAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_KODATE_LIST, ParseTokyuInvestKodateListFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_INVEST_KODATE_DETAIL, ParseTokyuInvestKodateDetailFuncAsync)
