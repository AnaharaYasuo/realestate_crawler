import os
import asyncio

from package.api.api import ApiAsyncProcBase, API_KEY_SUMIFU_DETAIL_GCP, API_KEY_SUMIFU_DETAIL, API_KEY_SUMIFU_REGION_GCP, \
API_KEY_SUMIFU_REGION, API_KEY_SUMIFU_AREA_GCP, API_KEY_SUMIFU_AREA, API_KEY_SUMIFU_LIST, API_KEY_SUMIFU_LIST_GCP, \
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
from package.parser.sumifuParser import SumifuMansionParser


class ParseSumifuDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")

    def _getLocalPararellLimit(self):
        return 10

    def _getCloudPararellLimit(self):
        return 10

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""
    

class ParseSumifuListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")

    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getLocalPararellLimit(self):
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_DETAIL_GCP
        return API_KEY_SUMIFU_DETAIL
    

class ParseSumifuAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return SumifuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 1200

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_LIST_GCP
        return API_KEY_SUMIFU_LIST


class ParseSumifuRegionFuncAsync(ParseMiddlePageAsyncBase):
    
    def _generateParser(self):
        return SumifuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRegionPage

    def _getLocalPararellLimit(self):
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_AREA_GCP
        return API_KEY_SUMIFU_AREA

    
class ParseSumifuStartAsync(ApiAsyncProcBase):

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
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_SUMIFU_REGION_GCP
        return API_KEY_SUMIFU_REGION

    def _callApi(self):
        return None

    async def _treatPage(self, _session, *arg):
        tasks = []
        _timeout = self._generateTimeout()

        for _detailUrl in self.urlList:
            task = asyncio.ensure_future(self._fetchWithEachSession(detailUrl=_detailUrl, apiUrl=self._getUrl() + self._getApiKey(), loop=self._getActiveEventLoop()))
            tasks.append(task)
        responses = await asyncio.gather(*tasks, loop=self._getActiveEventLoop())
        return responses

    def _getTreatPageArg(self):
        return 
