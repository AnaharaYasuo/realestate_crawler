
import os
import asyncio

from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_MISAWA_MANSION_START, API_KEY_MISAWA_MANSION_LIST, API_KEY_MISAWA_MANSION_DETAIL, \
    API_KEY_MISAWA_KODATE_START, API_KEY_MISAWA_KODATE_LIST, API_KEY_MISAWA_KODATE_DETAIL, \
    API_KEY_MISAWA_TOCHI_START, API_KEY_MISAWA_TOCHI_LIST, API_KEY_MISAWA_TOCHI_DETAIL, \
    API_KEY_MISAWA_INVEST_START, API_KEY_MISAWA_INVEST_KODATE_LIST, API_KEY_MISAWA_INVEST_KODATE_DETAIL, \
    API_KEY_MISAWA_INVEST_APARTMENT_LIST, API_KEY_MISAWA_INVEST_APARTMENT_DETAIL

from package.parser.misawaParser import MisawaParser
from package.api.registry import ApiRegistry

DEFAULT_PARARELL_LIMIT = 1
DETAIL_PARARELL_LIMIT = 1

# ==========================================
# Mansion (Type 1 -> Misawa Type 3)
# ==========================================

class ParseMisawaMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaMansionParser
        return MisawaMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMisawaMansionListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaMansionParser
        return MisawaMansionParser()

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
        return API_KEY_MISAWA_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MISAWA_MANSION_LIST

class ParseMisawaMansionStartAsync(ApiAsyncProcBase):
    # Mansion = Type 3 (Web ID)
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=3"]

    def _generateParser(self):
        from package.parser.misawaParser import MisawaMansionParser
        return MisawaMansionParser()

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return API_KEY_MISAWA_MANSION_LIST

    async def _callApi(self, urlList):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            # We skip 'Region'/'Area' layers and go straight to List for Misawa as the URL covers all
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses

    def _getTreatPageArg(self):
        return


# ==========================================
# Kodate (Type 2 -> Misawa Type 2)
# ==========================================

class ParseMisawaKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaKodateParser
        return MisawaKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMisawaKodateListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaKodateParser
        return MisawaKodateParser()

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
        return API_KEY_MISAWA_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MISAWA_KODATE_LIST

class ParseMisawaKodateStartAsync(ApiAsyncProcBase):
    # Kodate = Type 2 (Web ID)
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=2"]

    def _generateParser(self):
        from package.parser.misawaParser import MisawaKodateParser
        return MisawaKodateParser()

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return API_KEY_MISAWA_KODATE_LIST

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


# ==========================================
# Tochi (Type 3 -> Misawa Type 1)
# ==========================================

class ParseMisawaTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaTochiParser
        return MisawaTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMisawaTochiListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        from package.parser.misawaParser import MisawaTochiParser
        return MisawaTochiParser()

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
        return API_KEY_MISAWA_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MISAWA_TOCHI_LIST

class ParseMisawaTochiStartAsync(ApiAsyncProcBase):
    # Tochi = Type 1 (Web ID)
    urlList = ["https://realestate.misawa.co.jp/search/sale/list/?bukken_type[]=1"]

    def _generateParser(self):
        from package.parser.misawaParser import MisawaTochiParser
        return MisawaTochiParser()

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return API_KEY_MISAWA_TOCHI_LIST

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


# ==========================================
# Registry
# ==========================================

# Mansion
ApiRegistry.register(API_KEY_MISAWA_MANSION_START, ParseMisawaMansionStartAsync)
ApiRegistry.register(API_KEY_MISAWA_MANSION_LIST, ParseMisawaMansionListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_MANSION_DETAIL, ParseMisawaMansionDetailFuncAsync)

# Kodate
ApiRegistry.register(API_KEY_MISAWA_KODATE_START, ParseMisawaKodateStartAsync)
ApiRegistry.register(API_KEY_MISAWA_KODATE_LIST, ParseMisawaKodateListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_KODATE_DETAIL, ParseMisawaKodateDetailFuncAsync)

# Tochi
ApiRegistry.register(API_KEY_MISAWA_TOCHI_START, ParseMisawaTochiStartAsync)
ApiRegistry.register(API_KEY_MISAWA_TOCHI_LIST, ParseMisawaTochiListFuncAsync)
ApiRegistry.register(API_KEY_MISAWA_TOCHI_DETAIL, ParseMisawaTochiDetailFuncAsync)


