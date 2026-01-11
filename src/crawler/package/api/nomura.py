import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_NOMURA_PRO_START, API_KEY_NOMURA_PRO_START_GCP, \
    API_KEY_NOMURA_PRO_LIST, API_KEY_NOMURA_PRO_LIST_GCP, \
    API_KEY_NOMURA_PRO_DETAIL, API_KEY_NOMURA_PRO_DETAIL_GCP
from package.parser.nomuraParser import NomuraParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 2
DETAIL_PARALLEL_LIMIT = 5

class ParseNomuraProDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return NomuraParser("")

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

class ParseNomuraProListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return NomuraParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_PRO_LIST_GCP
        return API_KEY_NOMURA_PRO_LIST

    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_PRO_DETAIL_GCP
        return API_KEY_NOMURA_PRO_DETAIL

class ParseNomuraProStartAsync(ApiAsyncProcBase):
    # Start from the main search page
    urlList = ["https://www.nomu.com/pro/search/"]

    def _generateParser(self):
        return NomuraParser("")

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_NOMURA_PRO_LIST_GCP
        return API_KEY_NOMURA_PRO_LIST

    def _callApi(self):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            # First call sends to List API
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses

    def _getTreatPageArg(self):
        return

# Register APIs
ApiRegistry.register(API_KEY_NOMURA_PRO_START, ParseNomuraProStartAsync)
ApiRegistry.register(API_KEY_NOMURA_PRO_LIST, ParseNomuraProListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_PRO_DETAIL, ParseNomuraProDetailFuncAsync)
