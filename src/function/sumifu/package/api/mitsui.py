import os

from package.api.api import API_KEY_MITSUI_MANSION_DETAIL_GCP, API_KEY_MITSUI_MANSION_DETAIL, API_KEY_MITSUI_MANSION_AREA_GCP, API_KEY_MITSUI_MANSION_AREA, API_KEY_MITSUI_MANSION_LIST_GCP, API_KEY_MITSUI_MANSION_LIST
from package.api.api import API_KEY_MITSUI_TOCHI_AREA, API_KEY_MITSUI_TOCHI_AREA_GCP, API_KEY_MITSUI_TOCHI_DETAIL, API_KEY_MITSUI_TOCHI_DETAIL_GCP, API_KEY_MITSUI_TOCHI_LIST, API_KEY_MITSUI_TOCHI_LIST_GCP
from package.api.api import API_KEY_MITSUI_KODATE_AREA, API_KEY_MITSUI_KODATE_AREA_GCP, API_KEY_MITSUI_KODATE_DETAIL, API_KEY_MITSUI_KODATE_DETAIL_GCP, API_KEY_MITSUI_KODATE_LIST, API_KEY_MITSUI_KODATE_LIST_GCP
from package.api.api import ParseDetailPageAsyncBase,ParseMiddlePageAsyncBase
from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiTochiParser, MitsuiKodateParser

DEFAULT_PARARELL_LIMIT = 2
DETAIL_PARARELL_LIMIT = 6

class ParseMitsuiMansionDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")

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
    
class ParseMitsuiMansionListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
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
            return API_KEY_MITSUI_MANSION_DETAIL_GCP
        return API_KEY_MITSUI_MANSION_DETAIL

    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_MANSION_LIST_GCP
        return API_KEY_MITSUI_MANSION_LIST
    

class ParseMitsuiMansionAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
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
            return API_KEY_MITSUI_MANSION_LIST_GCP
        return API_KEY_MITSUI_MANSION_LIST
    
class ParseMitsuiMansionStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
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
            return API_KEY_MITSUI_MANSION_AREA_GCP
        return API_KEY_MITSUI_MANSION_AREA

class ParseMitsuiTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    
    def _generateParser(self):
        return MitsuiTochiParser("")

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
    
class ParseMitsuiTochiListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiTochiParser("")
    
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
            return API_KEY_MITSUI_TOCHI_DETAIL_GCP
        return API_KEY_MITSUI_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_TOCHI_LIST_GCP
        return API_KEY_MITSUI_TOCHI_LIST    

class ParseMitsuiTochiAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiTochiParser("")
    
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
            return API_KEY_MITSUI_TOCHI_LIST_GCP
        return API_KEY_MITSUI_TOCHI_LIST
    
class ParseMitsuiTochiStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiTochiParser("")
    
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
            return API_KEY_MITSUI_TOCHI_AREA_GCP
        return API_KEY_MITSUI_TOCHI_AREA


class ParseMitsuiKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    
    def _generateParser(self):
        return MitsuiKodateParser("")

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
    
class ParseMitsuiKodateListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiKodateParser("")
    
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
            return API_KEY_MITSUI_KODATE_DETAIL_GCP
        return API_KEY_MITSUI_KODATE_DETAIL

    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_KODATE_LIST_GCP
        return API_KEY_MITSUI_KODATE_LIST

class ParseMitsuiKodateAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiKodateParser("")
    
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
            return API_KEY_MITSUI_KODATE_LIST_GCP
        return API_KEY_MITSUI_KODATE_LIST
    
class ParseMitsuiKodateStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiKodateParser("")
    
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
            return API_KEY_MITSUI_KODATE_AREA_GCP
        return API_KEY_MITSUI_KODATE_AREA
