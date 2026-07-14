# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_DAIKYO_MANSION_START, API_KEY_DAIKYO_MANSION_DETAIL,
    API_KEY_DAIKYO_KODATE_START, API_KEY_DAIKYO_KODATE_DETAIL,
    API_KEY_DAIKYO_TOCHI_START, API_KEY_DAIKYO_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.daikyoParser import (
    DaikyoMansionParser, DaikyoKodateParser, DaikyoTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseDaikyoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return DaikyoMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseDaikyoMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return DaikyoMansionParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_DAIKYO_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_DAIKYO_MANSION_START

# Kodate
class ParseDaikyoKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return DaikyoKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseDaikyoKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return DaikyoKodateParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_DAIKYO_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_DAIKYO_KODATE_START

# Tochi
class ParseDaikyoTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return DaikyoTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseDaikyoTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return DaikyoTochiParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_DAIKYO_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_DAIKYO_TOCHI_START

# Register
ApiRegistry.register(API_KEY_DAIKYO_MANSION_START, ParseDaikyoMansionStartAsync)
ApiRegistry.register(API_KEY_DAIKYO_MANSION_DETAIL, ParseDaikyoMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_DAIKYO_KODATE_START, ParseDaikyoKodateStartAsync)
ApiRegistry.register(API_KEY_DAIKYO_KODATE_DETAIL, ParseDaikyoKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_DAIKYO_TOCHI_START, ParseDaikyoTochiStartAsync)
ApiRegistry.register(API_KEY_DAIKYO_TOCHI_DETAIL, ParseDaikyoTochiDetailFuncAsync)
