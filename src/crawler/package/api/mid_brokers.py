from package.api.api import (
    API_KEY_ADCAST_KODATE_DETAIL,
    API_KEY_ADCAST_KODATE_START,
    API_KEY_ADCAST_TOCHI_DETAIL,
    API_KEY_ADCAST_TOCHI_START,
    API_KEY_HASEKO_MANSION_DETAIL,
    API_KEY_HASEKO_MANSION_START,
    API_KEY_IETAN_KODATE_DETAIL,
    API_KEY_IETAN_KODATE_START,
    API_KEY_IETAN_MANSION_DETAIL,
    API_KEY_IETAN_MANSION_START,
    API_KEY_IETAN_TOCHI_DETAIL,
    API_KEY_IETAN_TOCHI_START,
    API_KEY_TOHO_KODATE_DETAIL,
    API_KEY_TOHO_KODATE_START,
    API_KEY_TOHO_MANSION_DETAIL,
    API_KEY_TOHO_MANSION_START,
    API_KEY_TOHO_TOCHI_DETAIL,
    API_KEY_TOHO_TOCHI_START,
    ParseDetailPageAsyncBase,
    ParseMiddlePageAsyncBase,
)
from package.api.registry import ApiRegistry
from package.parser.adcastParser import AdCastKodateParser, AdCastTochiParser
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.ietanParser import (
    IetanKodateParser,
    IetanMansionParser,
    IetanTochiParser,
)
from package.parser.tohoParser import (
    TohoKodateParser,
    TohoMansionParser,
    TohoTochiParser,
)

DETAIL_PARALLEL_LIMIT = 3
MIDDLE_PARALLEL_LIMIT = 3

# --- Ietan ---
class ParseIetanMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return IetanMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseIetanMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return IetanMansionParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_IETAN_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_IETAN_MANSION_START

class ParseIetanKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return IetanKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseIetanKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return IetanKodateParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_IETAN_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_IETAN_KODATE_START

class ParseIetanTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return IetanTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseIetanTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return IetanTochiParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_IETAN_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_IETAN_TOCHI_START

# --- Haseko ---
class ParseHasekoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return HasekoMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseHasekoMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return HasekoMansionParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_HASEKO_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_HASEKO_MANSION_START

# --- AdCast ---
class ParseAdCastKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return AdCastKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseAdCastKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return AdCastKodateParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_ADCAST_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_ADCAST_KODATE_START

class ParseAdCastTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return AdCastTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseAdCastTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return AdCastTochiParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_ADCAST_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_ADCAST_TOCHI_START

# --- Toho ---
class ParseTohoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return TohoMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseTohoMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return TohoMansionParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_TOHO_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_TOHO_MANSION_START

class ParseTohoKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return TohoKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseTohoKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return TohoKodateParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_TOHO_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_TOHO_KODATE_START

class ParseTohoTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return TohoTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseTohoTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return TohoTochiParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_TOHO_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_TOHO_TOCHI_START

# Register
ApiRegistry.register(API_KEY_IETAN_MANSION_START, ParseIetanMansionStartAsync)
ApiRegistry.register(API_KEY_IETAN_MANSION_DETAIL, ParseIetanMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_IETAN_KODATE_START, ParseIetanKodateStartAsync)
ApiRegistry.register(API_KEY_IETAN_KODATE_DETAIL, ParseIetanKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_IETAN_TOCHI_START, ParseIetanTochiStartAsync)
ApiRegistry.register(API_KEY_IETAN_TOCHI_DETAIL, ParseIetanTochiDetailFuncAsync)

ApiRegistry.register(API_KEY_HASEKO_MANSION_START, ParseHasekoMansionStartAsync)
ApiRegistry.register(API_KEY_HASEKO_MANSION_DETAIL, ParseHasekoMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_ADCAST_KODATE_START, ParseAdCastKodateStartAsync)
ApiRegistry.register(API_KEY_ADCAST_KODATE_DETAIL, ParseAdCastKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_ADCAST_TOCHI_START, ParseAdCastTochiStartAsync)
ApiRegistry.register(API_KEY_ADCAST_TOCHI_DETAIL, ParseAdCastTochiDetailFuncAsync)

ApiRegistry.register(API_KEY_TOHO_MANSION_START, ParseTohoMansionStartAsync)
ApiRegistry.register(API_KEY_TOHO_MANSION_DETAIL, ParseTohoMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_TOHO_KODATE_START, ParseTohoKodateStartAsync)
ApiRegistry.register(API_KEY_TOHO_KODATE_DETAIL, ParseTohoKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_TOHO_TOCHI_START, ParseTohoTochiStartAsync)
ApiRegistry.register(API_KEY_TOHO_TOCHI_DETAIL, ParseTohoTochiDetailFuncAsync)
