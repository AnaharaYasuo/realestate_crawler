import os

from package.api.api import API_KEY_TOKYU_DETAIL_GCP, API_KEY_TOKYU_DETAIL, API_KEY_TOKYU_AREA_GCP, API_KEY_TOKYU_AREA, API_KEY_TOKYU_LIST_GCP, API_KEY_TOKYU_LIST, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
from package.parser.tokyuParser import TokyuMansionParser


class ParseTokyuDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")

    def _getLocalPararellLimit(self):
        return 8

    def _getCloudPararellLimit(self):
        return 8

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""

    
class ParseTokyuListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.getPropertyListNextPageUrl

    def _getLocalPararellLimit(self):
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_DETAIL_GCP
        return API_KEY_TOKYU_DETAIL
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_LIST_GCP
        return API_KEY_TOKYU_LIST

class ParseTokyuAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return 2

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_LIST_GCP
        return API_KEY_TOKYU_LIST

    
class ParseTokyuStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 2

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_AREA_GCP
        return API_KEY_TOKYU_AREA
