# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_SOTETSU_MANSION_START, API_KEY_SOTETSU_MANSION_DETAIL,
    API_KEY_SOTETSU_KODATE_START, API_KEY_SOTETSU_KODATE_DETAIL,
    API_KEY_SOTETSU_TOCHI_START, API_KEY_SOTETSU_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.sotetsuParser import (
    SotetsuMansionParser, SotetsuKodateParser, SotetsuTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseSotetsuMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SotetsuMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSotetsuMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SotetsuMansionParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SOTETSU_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SOTETSU_MANSION_START

# Kodate
class ParseSotetsuKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SotetsuKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSotetsuKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SotetsuKodateParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SOTETSU_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SOTETSU_KODATE_START

# Tochi
class ParseSotetsuTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SotetsuTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSotetsuTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SotetsuTochiParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SOTETSU_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SOTETSU_TOCHI_START

# Register
ApiRegistry.register(API_KEY_SOTETSU_MANSION_START, ParseSotetsuMansionStartAsync)
ApiRegistry.register(API_KEY_SOTETSU_MANSION_DETAIL, ParseSotetsuMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_SOTETSU_KODATE_START, ParseSotetsuKodateStartAsync)
ApiRegistry.register(API_KEY_SOTETSU_KODATE_DETAIL, ParseSotetsuKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_SOTETSU_TOCHI_START, ParseSotetsuTochiStartAsync)
ApiRegistry.register(API_KEY_SOTETSU_TOCHI_DETAIL, ParseSotetsuTochiDetailFuncAsync)
