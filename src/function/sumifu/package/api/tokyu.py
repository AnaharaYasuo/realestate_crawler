import os

from package.api.api import API_KEY_TOKYU_MANSION_DETAIL_GCP, API_KEY_TOKYU_MANSION_DETAIL, API_KEY_TOKYU_MANSION_AREA_GCP, API_KEY_TOKYU_MANSION_AREA, API_KEY_TOKYU_MANSION_LIST_GCP, API_KEY_TOKYU_MANSION_LIST, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
from package.parser.tokyuParser import TokyuMansionParser

DEFAULT_PARARELL_LIMIT = 2
DETAIL_PARARELL_LIMIT = 6

class ParseTokyuMansionDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")

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

    
class ParseTokyuMansionListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.getPropertyListNextPageUrl

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 360

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_MANSION_DETAIL_GCP
        return API_KEY_TOKYU_MANSION_DETAIL
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_MANSION_LIST_GCP
        return API_KEY_TOKYU_MANSION_LIST

class ParseTokyuMansionAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_MANSION_LIST_GCP
        return API_KEY_TOKYU_MANSION_LIST

    
class ParseTokyuMansionStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_TOKYU_MANSION_AREA_GCP
        return API_KEY_TOKYU_MANSION_AREA
