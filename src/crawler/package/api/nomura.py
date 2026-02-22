import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_NOMURA_MANSION_START, API_KEY_NOMURA_MANSION_REGION, API_KEY_NOMURA_MANSION_AREA, API_KEY_NOMURA_MANSION_LIST, API_KEY_NOMURA_MANSION_DETAIL, \
    API_KEY_NOMURA_MANSION_REGION_GCP, API_KEY_NOMURA_MANSION_AREA_GCP, API_KEY_NOMURA_MANSION_LIST_GCP, API_KEY_NOMURA_MANSION_DETAIL_GCP, \
    API_KEY_NOMURA_KODATE_START, API_KEY_NOMURA_KODATE_REGION, API_KEY_NOMURA_KODATE_AREA, API_KEY_NOMURA_KODATE_LIST, API_KEY_NOMURA_KODATE_DETAIL, \
    API_KEY_NOMURA_KODATE_REGION_GCP, API_KEY_NOMURA_KODATE_AREA_GCP, API_KEY_NOMURA_KODATE_LIST_GCP, API_KEY_NOMURA_KODATE_DETAIL_GCP, \
    API_KEY_NOMURA_TOCHI_START, API_KEY_NOMURA_TOCHI_REGION, API_KEY_NOMURA_TOCHI_AREA, API_KEY_NOMURA_TOCHI_LIST, API_KEY_NOMURA_TOCHI_DETAIL, \
    API_KEY_NOMURA_TOCHI_REGION_GCP, API_KEY_NOMURA_TOCHI_AREA_GCP, API_KEY_NOMURA_TOCHI_LIST_GCP, API_KEY_NOMURA_TOCHI_DETAIL_GCP
    
from package.parser.nomuraParser import NomuraMansionParser, NomuraKodateParser, NomuraTochiParser
from package.api.registry import ApiRegistry

DEFAULT_PARARELL_LIMIT = 1
DETAIL_PARARELL_LIMIT = 1

def _get_combined_parser(self):
    async def combined_parser(response):
        # 1. Properties (on list pages)
        async for item in self.parser.parsePropertyListPage(response):
            yield item
        # 2. Deeper regions
        async for url in self.parser.parseRegionPage(response):
            yield url
    return combined_parser

def _get_area_combined_parser(self):
    async def combined_parser(response):
        # 1. Properties (on list pages)
        async for item in self.parser.parsePropertyListPage(response):
            yield item
        # 2. Deeper areas
        async for url in self.parser.parseAreaPage(response):
            yield url
    return combined_parser

# ==============================================================================
#  Mansion
# ==============================================================================

class ParseNomuraMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return NomuraMansionParser("")
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseNomuraMansionListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraMansionParser("")
    def _getParserFunc(self): return self.parser.parsePropertyListPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 360
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_MANSION_DETAIL_GCP
        return API_KEY_NOMURA_MANSION_DETAIL
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_MANSION_LIST_GCP
        return API_KEY_NOMURA_MANSION_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraMansionAreaFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraMansionParser("")
    def _getParserFunc(self): return _get_area_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_MANSION_LIST_GCP
        return API_KEY_NOMURA_MANSION_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraMansionRegionFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraMansionParser("")
    def _getParserFunc(self): return _get_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_MANSION_AREA_GCP
        return API_KEY_NOMURA_MANSION_AREA
    def _isBsMiddlePage(self): return True

class ParseNomuraMansionStartAsync(ApiAsyncProcBase):
    urlList = [
        "https://www.nomu.com/mansion/ensen_tokyo/2171/2171110/",
        "https://www.nomu.com/mansion/ensen_tokyo/2172/2172110/",
    ]
    def _generateParser(self): return NomuraMansionParser("")
    def _getLocalPararellLimit(self): return 5
    def _getCloudPararellLimit(self): return 5
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_MANSION_REGION_GCP
        return API_KEY_NOMURA_MANSION_REGION
    async def _callApi(self, urlList): return None
    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
            await asyncio.sleep(0.1)
        responses = await asyncio.gather(*tasks)
        return responses
    def _getTreatPageArg(self): return

# ==============================================================================
#  Kodate
# ==============================================================================

class ParseNomuraKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return NomuraKodateParser("")
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseNomuraKodateListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraKodateParser("")
    def _getParserFunc(self): return self.parser.parsePropertyListPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 360
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_KODATE_DETAIL_GCP
        return API_KEY_NOMURA_KODATE_DETAIL
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_KODATE_LIST_GCP
        return API_KEY_NOMURA_KODATE_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraKodateAreaFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraKodateParser("")
    def _getParserFunc(self): return _get_area_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_KODATE_LIST_GCP
        return API_KEY_NOMURA_KODATE_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraKodateRegionFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraKodateParser("")
    def _getParserFunc(self): return _get_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_KODATE_AREA_GCP
        return API_KEY_NOMURA_KODATE_AREA
    def _isBsMiddlePage(self): return True

class ParseNomuraKodateStartAsync(ApiAsyncProcBase):
    urlList = [
        "https://www.nomu.com/house/ensen_tokyo/",
        "https://www.nomu.com/house/ensen_kanagawa/",
        "https://www.nomu.com/house/ensen_saitama/",
        "https://www.nomu.com/house/ensen_chiba/",
    ]
    def _generateParser(self): return NomuraKodateParser("")
    def _getLocalPararellLimit(self): return 5
    def _getCloudPararellLimit(self): return 5
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_KODATE_REGION_GCP
        return API_KEY_NOMURA_KODATE_REGION
    async def _callApi(self, urlList): return None
    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
            await asyncio.sleep(0.1)
        responses = await asyncio.gather(*tasks)
        return responses
    def _getTreatPageArg(self): return

# ==============================================================================
#  Tochi
# ==============================================================================

class ParseNomuraTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return NomuraTochiParser("")
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseNomuraTochiListFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraTochiParser("")
    def _getParserFunc(self): return self.parser.parsePropertyListPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 360
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_TOCHI_DETAIL_GCP
        return API_KEY_NOMURA_TOCHI_DETAIL
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_TOCHI_LIST_GCP
        return API_KEY_NOMURA_TOCHI_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraTochiAreaFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraTochiParser("")
    def _getParserFunc(self): return _get_area_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_TOCHI_LIST_GCP
        return API_KEY_NOMURA_TOCHI_LIST
    def _isBsMiddlePage(self): return True

class ParseNomuraTochiRegionFuncAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return NomuraTochiParser("")
    def _getParserFunc(self): return _get_combined_parser(self)
    def _getLocalPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DEFAULT_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_TOCHI_AREA_GCP
        return API_KEY_NOMURA_TOCHI_AREA
    def _isBsMiddlePage(self): return True

class ParseNomuraTochiStartAsync(ApiAsyncProcBase):
    urlList = [
        "https://www.nomu.com/land/ensen_tokyo/",
        "https://www.nomu.com/land/ensen_kanagawa/",
        "https://www.nomu.com/land/ensen_saitama/",
        "https://www.nomu.com/land/ensen_chiba/",
    ]
    def _generateParser(self): return NomuraTochiParser("")
    def _getLocalPararellLimit(self): return 5
    def _getCloudPararellLimit(self): return 5
    def _getTimeOutSecond(self): return 2400
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''): return API_KEY_NOMURA_TOCHI_REGION_GCP
        return API_KEY_NOMURA_TOCHI_REGION
    async def _callApi(self, urlList): return None
    async def _treatPage(self, _session, *arg):
        tasks = []
        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
            await asyncio.sleep(0.1)
        responses = await asyncio.gather(*tasks)
        return responses
    def _getTreatPageArg(self): return

# ==============================================================================
#  Registry
# ==============================================================================

# Mansion
ApiRegistry.register(API_KEY_NOMURA_MANSION_START, ParseNomuraMansionStartAsync)
ApiRegistry.register(API_KEY_NOMURA_MANSION_REGION, ParseNomuraMansionRegionFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_MANSION_AREA, ParseNomuraMansionAreaFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_MANSION_LIST, ParseNomuraMansionListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_MANSION_DETAIL, ParseNomuraMansionDetailFuncAsync)

# Kodate
ApiRegistry.register(API_KEY_NOMURA_KODATE_START, ParseNomuraKodateStartAsync)
ApiRegistry.register(API_KEY_NOMURA_KODATE_REGION, ParseNomuraKodateRegionFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_KODATE_AREA, ParseNomuraKodateAreaFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_KODATE_LIST, ParseNomuraKodateListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_KODATE_DETAIL, ParseNomuraKodateDetailFuncAsync)

# Tochi
ApiRegistry.register(API_KEY_NOMURA_TOCHI_START, ParseNomuraTochiStartAsync)
ApiRegistry.register(API_KEY_NOMURA_TOCHI_REGION, ParseNomuraTochiRegionFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_TOCHI_AREA, ParseNomuraTochiAreaFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_TOCHI_LIST, ParseNomuraTochiListFuncAsync)
ApiRegistry.register(API_KEY_NOMURA_TOCHI_DETAIL, ParseNomuraTochiDetailFuncAsync)
