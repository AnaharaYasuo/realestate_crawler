
import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_NOMURA_INVEST_KODATE_START, API_KEY_NOMURA_INVEST_KODATE_LIST, API_KEY_NOMURA_INVEST_KODATE_DETAIL, \
    API_KEY_NOMURA_INVEST_KODATE_START_GCP, API_KEY_NOMURA_INVEST_KODATE_LIST_GCP, API_KEY_NOMURA_INVEST_KODATE_DETAIL_GCP, \
    API_KEY_NOMURA_INVEST_APARTMENT_START, API_KEY_NOMURA_INVEST_APARTMENT_LIST, API_KEY_NOMURA_INVEST_APARTMENT_DETAIL, \
    API_KEY_NOMURA_INVEST_APARTMENT_START_GCP, API_KEY_NOMURA_INVEST_APARTMENT_LIST_GCP, API_KEY_NOMURA_INVEST_APARTMENT_DETAIL_GCP

from package.parser.nomuraParser import NomuraInvestmentKodateParser, NomuraInvestmentApartmentParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 1
DETAIL_PARALLEL_LIMIT = 1

# ==============================================================================
#  BASE CLASSES
# ==============================================================================

class ParseNomuraInvestDetailFuncAsyncBase(ParseDetailPageAsyncBase):
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

class ParseNomuraInvestListFuncAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage

    def _isBsMiddlePage(self):
        return True
    
    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _isBsMiddlePage(self):
        return True

class ParseNomuraInvestStartAsyncBase(ApiAsyncProcBase):
    # TODO: Identify URL parameter
    urlList = ["https://www.nomu.com/pro/"]

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

class ParseNomuraInvestKodateDetailFuncAsync(ParseNomuraInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return NomuraInvestmentKodateParser("")

class ParseNomuraInvestKodateListFuncAsync(ParseNomuraInvestListFuncAsyncBase):
    def _generateParser(self):
        return NomuraInvestmentKodateParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_KODATE_LIST_GCP
        return API_KEY_NOMURA_INVEST_KODATE_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_KODATE_DETAIL_GCP
        return API_KEY_NOMURA_INVEST_KODATE_DETAIL

class ParseNomuraInvestKodateStartAsync(ParseNomuraInvestStartAsyncBase):
    # Updated to specific category page
    urlList = ["https://www.nomu.com/pro/house/"]

    def _generateParser(self):
        return NomuraInvestmentKodateParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_KODATE_LIST_GCP
        return API_KEY_NOMURA_INVEST_KODATE_LIST

# ==============================================================================
#  APARTMENT (アパート)
# ==============================================================================

class ParseNomuraInvestApartmentDetailFuncAsync(ParseNomuraInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return NomuraInvestmentApartmentParser("")

class ParseNomuraInvestApartmentListFuncAsync(ParseNomuraInvestListFuncAsyncBase):
    def _generateParser(self):
        return NomuraInvestmentApartmentParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_APARTMENT_LIST_GCP
        return API_KEY_NOMURA_INVEST_APARTMENT_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_APARTMENT_DETAIL_GCP
        return API_KEY_NOMURA_INVEST_APARTMENT_DETAIL

class ParseNomuraInvestApartmentStartAsync(ParseNomuraInvestStartAsyncBase):
    # アパート専用パスのみを取得
    urlList = [
        "https://www.nomu.com/pro/apart/"
    ]

    def _generateParser(self):
        return NomuraInvestmentApartmentParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_INVEST_APARTMENT_LIST_GCP
        return API_KEY_NOMURA_INVEST_APARTMENT_LIST

# ==============================================================================
#  REGISTRY
# ==============================================================================

# Kodate
ApiRegistry.register(API_KEY_NOMURA_INVEST_KODATE_START, ParseNomuraInvestKodateStartAsync)
ApiRegistry.register(API_KEY_NOMURA_INVEST_KODATE_LIST, ParseNomuraInvestKodateListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_INVEST_KODATE_DETAIL, ParseNomuraInvestKodateDetailFuncAsync)

# Apartment
ApiRegistry.register(API_KEY_NOMURA_INVEST_APARTMENT_START, ParseNomuraInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_NOMURA_INVEST_APARTMENT_LIST, ParseNomuraInvestApartmentListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_INVEST_APARTMENT_DETAIL, ParseNomuraInvestApartmentDetailFuncAsync)
