import os
import asyncio

from package.api.api import ApiAsyncProcBase, API_KEY_SUMIFU_MANSION_DETAIL_GCP, API_KEY_SUMIFU_MANSION_DETAIL, API_KEY_SUMIFU_MANSION_REGION_GCP, \
API_KEY_SUMIFU_MANSION_REGION, API_KEY_SUMIFU_MANSION_AREA_GCP, API_KEY_SUMIFU_MANSION_AREA, API_KEY_SUMIFU_MANSION_LIST, API_KEY_SUMIFU_MANSION_LIST_GCP, API_KEY_SUMIFU_MANSION_START, \
API_KEY_SUMIFU_TOCHI_DETAIL, API_KEY_SUMIFU_TOCHI_REGION, API_KEY_SUMIFU_TOCHI_AREA, API_KEY_SUMIFU_TOCHI_LIST, \
API_KEY_SUMIFU_TOCHI_DETAIL_GCP, API_KEY_SUMIFU_TOCHI_REGION_GCP, API_KEY_SUMIFU_TOCHI_AREA_GCP, API_KEY_SUMIFU_TOCHI_LIST_GCP, API_KEY_SUMIFU_TOCHI_START, \
API_KEY_SUMIFU_KODATE_DETAIL, API_KEY_SUMIFU_KODATE_REGION, API_KEY_SUMIFU_KODATE_AREA, API_KEY_SUMIFU_KODATE_LIST, \
API_KEY_SUMIFU_KODATE_DETAIL_GCP, API_KEY_SUMIFU_KODATE_REGION_GCP, API_KEY_SUMIFU_KODATE_AREA_GCP, API_KEY_SUMIFU_KODATE_LIST_GCP, API_KEY_SUMIFU_KODATE_START, \
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
from package.parser.sumifuParser import SumifuMansionParser,SumifuTochiParser,SumifuKodateParser

DEFAULT_PARARELL_LIMIT = 2
DETAIL_PARARELL_LIMIT = 6

class ParseSumifuMansionDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""
    

class ParseSumifuMansionListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_MANSION_DETAIL_GCP
        return API_KEY_SUMIFU_MANSION_DETAIL
    

class ParseSumifuMansionAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_MANSION_LIST_GCP
        return API_KEY_SUMIFU_MANSION_LIST


class ParseSumifuMansionRegionFuncAsync(ParseMiddlePageAsyncBase):
    
    def _generateParser(self):
        return SumifuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRegionPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_MANSION_AREA_GCP
        return API_KEY_SUMIFU_MANSION_AREA

    
class ParseSumifuMansionStartAsync(ApiAsyncProcBase):

    urlList = ["https://www.stepon.co.jp/mansion/tokai/"
    , "https://www.stepon.co.jp/mansion/shutoken/"
    , "https://www.stepon.co.jp/mansion/kansai/"
    , "https://www.stepon.co.jp/mansion/hokkaido/"
    , "https://www.stepon.co.jp/mansion/tohoku/"
    , "https://www.stepon.co.jp/mansion/chugoku/"
    , "https://www.stepon.co.jp/mansion/kyushu/"]
    
    def _generateParser(self):
        return SumifuMansionParser("")

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_MANSION_REGION_GCP
        return API_KEY_SUMIFU_MANSION_REGION

    def _callApi(self):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        _timeout = self._generateTimeout()

        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks) # Fixed: removed loop argument
        return responses

    def _getTreatPageArg(self):
        return 

class ParseSumifuTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    
    def _generateParser(self):
        return SumifuTochiParser("")

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""
    

class ParseSumifuTochiListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuTochiParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_TOCHI_DETAIL_GCP
        return API_KEY_SUMIFU_TOCHI_DETAIL
    

class ParseSumifuTochiAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuTochiParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_TOCHI_LIST_GCP
        return API_KEY_SUMIFU_TOCHI_LIST


class ParseSumifuTochiRegionFuncAsync(ParseMiddlePageAsyncBase):
    
    def _generateParser(self):
        return SumifuTochiParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRegionPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_TOCHI_AREA_GCP
        return API_KEY_SUMIFU_TOCHI_AREA

    
class ParseSumifuTochiStartAsync(ApiAsyncProcBase):

    urlList = ["https://www.stepon.co.jp/tochi/tokai/"
    , "https://www.stepon.co.jp/tochi/shutoken/"
    , "https://www.stepon.co.jp/tochi/kansai/"
    , "https://www.stepon.co.jp/tochi/hokkaido/"
    , "https://www.stepon.co.jp/tochi/tohoku/"
    , "https://www.stepon.co.jp/tochi/chugoku/"
    , "https://www.stepon.co.jp/tochi/kyushu/"]
    
    def _generateParser(self):
        return SumifuTochiParser("")

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_TOCHI_REGION_GCP
        return API_KEY_SUMIFU_TOCHI_REGION

    def _callApi(self):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        _timeout = self._generateTimeout()

        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks) # Fixed: removed loop argument
        return responses

    def _getTreatPageArg(self):
        return 

class ParseSumifuKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    
    def _generateParser(self):
        return SumifuKodateParser("")

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""
    

class ParseSumifuKodateListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuKodateParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_KODATE_DETAIL_GCP
        return API_KEY_SUMIFU_KODATE_DETAIL
    

class ParseSumifuKodateAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuKodateParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_KODATE_LIST_GCP
        return API_KEY_SUMIFU_KODATE_LIST


class ParseSumifuKodateRegionFuncAsync(ParseMiddlePageAsyncBase):
    
    def _generateParser(self):
        return SumifuKodateParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRegionPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_KODATE_AREA_GCP
        return API_KEY_SUMIFU_KODATE_AREA

    
class ParseSumifuKodateStartAsync(ApiAsyncProcBase):

    urlList = ["https://www.stepon.co.jp/kodate/tokai/"
    , "https://www.stepon.co.jp/kodate/shutoken/"
    , "https://www.stepon.co.jp/kodate/kansai/"
    , "https://www.stepon.co.jp/kodate/hokkaido/"
    , "https://www.stepon.co.jp/kodate/tohoku/"
    , "https://www.stepon.co.jp/kodate/chugoku/"
    , "https://www.stepon.co.jp/kodate/kyushu/"]
    
    def _generateParser(self):
        return SumifuKodateParser("")

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_KODATE_REGION_GCP
        return API_KEY_SUMIFU_KODATE_REGION

    def _callApi(self):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        _timeout = self._generateTimeout()

        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks) # Fixed: removed loop argument
        return responses

    def _getTreatPageArg(self):
        return 

from package.api.registry import ApiRegistry

# Mansion
ApiRegistry.register(API_KEY_SUMIFU_MANSION_START, ParseSumifuMansionStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_MANSION_REGION, ParseSumifuMansionRegionFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_MANSION_AREA, ParseSumifuMansionAreaFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_MANSION_LIST, ParseSumifuMansionListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_MANSION_DETAIL, ParseSumifuMansionDetailFuncAsync)

# Tochi
ApiRegistry.register(API_KEY_SUMIFU_TOCHI_START, ParseSumifuTochiStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_TOCHI_REGION, ParseSumifuTochiRegionFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_TOCHI_AREA, ParseSumifuTochiAreaFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_TOCHI_LIST, ParseSumifuTochiListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_TOCHI_DETAIL, ParseSumifuTochiDetailFuncAsync)

# Kodate
ApiRegistry.register(API_KEY_SUMIFU_KODATE_START, ParseSumifuKodateStartAsync)
ApiRegistry.register(API_KEY_SUMIFU_KODATE_REGION, ParseSumifuKodateRegionFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_KODATE_AREA, ParseSumifuKodateAreaFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_KODATE_LIST, ParseSumifuKodateListFuncAsync)
ApiRegistry.register(API_KEY_SUMIFU_KODATE_DETAIL, ParseSumifuKodateDetailFuncAsync) 
