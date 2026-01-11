import os

from package.api.api import API_KEY_TOKYU_MANSION_DETAIL_GCP, API_KEY_TOKYU_MANSION_DETAIL, API_KEY_TOKYU_MANSION_AREA_GCP, API_KEY_TOKYU_MANSION_AREA, API_KEY_TOKYU_MANSION_LIST_GCP, API_KEY_TOKYU_MANSION_LIST, API_KEY_TOKYU_MANSION_START
from package.api.api import API_KEY_TOKYU_TOCHI_START, API_KEY_TOKYU_TOCHI_AREA, API_KEY_TOKYU_TOCHI_LIST, API_KEY_TOKYU_TOCHI_DETAIL
from package.api.api import API_KEY_TOKYU_KODATE_START, API_KEY_TOKYU_KODATE_AREA, API_KEY_TOKYU_KODATE_LIST, API_KEY_TOKYU_KODATE_DETAIL, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
from package.parser.tokyuParser import TokyuMansionParser, TokyuTochiParser, TokyuKodateParser

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


###################################################
# tokyu tochi
###################################################
class ParseTokyuTochiDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return TokyuTochiParser("")

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
    
class ParseTokyuTochiListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuTochiParser("")
    
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
        # TODO: Define specific API keys for Tochi in api.py if needed, effectively using same pattern
        return "/api/tokyu/tochi/detail" 
    
    def _getNextPageApiKey(self):
        return "/api/tokyu/tochi/list"

class ParseTokyuTochiStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuTochiParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return "/api/tokyu/tochi/area"

class ParseTokyuTochiAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuTochiParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return "/api/tokyu/tochi/list"


###################################################
# tokyu kodate
###################################################
class ParseTokyuKodateDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return TokyuKodateParser("")

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
    
class ParseTokyuKodateListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuKodateParser("")
    
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
        return "/api/tokyu/kodate/detail"
    
    def _getNextPageApiKey(self):
        return "/api/tokyu/kodate/list"


class ParseTokyuKodateStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuKodateParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return "/api/tokyu/kodate/area"

class ParseTokyuKodateAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return TokyuKodateParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

    def _getApiKey(self):
        return "/api/tokyu/kodate/list"

from package.api.registry import ApiRegistry

# Mansion
ApiRegistry.register(API_KEY_TOKYU_MANSION_START, ParseTokyuMansionStartAsync)
ApiRegistry.register(API_KEY_TOKYU_MANSION_AREA, ParseTokyuMansionAreaFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_MANSION_LIST, ParseTokyuMansionListFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_MANSION_DETAIL, ParseTokyuMansionDetailFuncAsync)

# Tochi
ApiRegistry.register(API_KEY_TOKYU_TOCHI_START, ParseTokyuTochiStartAsync)
ApiRegistry.register(API_KEY_TOKYU_TOCHI_AREA, ParseTokyuTochiAreaFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_TOCHI_LIST, ParseTokyuTochiListFuncAsync)
# Note: Detail key might be hardcoded in tokyu.py as "/api/tokyu/tochi/detail" but let's use the constant if available or string
ApiRegistry.register(API_KEY_TOKYU_TOCHI_DETAIL, ParseTokyuTochiDetailFuncAsync)

# Kodate
ApiRegistry.register(API_KEY_TOKYU_KODATE_START, ParseTokyuKodateStartAsync)
ApiRegistry.register(API_KEY_TOKYU_KODATE_AREA, ParseTokyuKodateAreaFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_KODATE_LIST, ParseTokyuKodateListFuncAsync)
ApiRegistry.register(API_KEY_TOKYU_KODATE_DETAIL, ParseTokyuKodateDetailFuncAsync)
