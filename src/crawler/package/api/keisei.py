# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_KEISEI_MANSION_START, API_KEY_KEISEI_MANSION_DETAIL,
    API_KEY_KEISEI_KODATE_START, API_KEY_KEISEI_KODATE_DETAIL,
    API_KEY_KEISEI_TOCHI_START, API_KEY_KEISEI_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.keiseiParser import (
    KeiseiMansionParser, KeiseiKodateParser, KeiseiTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseKeiseiMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeiseiMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeiseiMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeiseiMansionParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEISEI_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEISEI_MANSION_START

# Kodate
class ParseKeiseiKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeiseiKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeiseiKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeiseiKodateParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEISEI_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEISEI_KODATE_START

# Tochi
class ParseKeiseiTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeiseiTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeiseiTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeiseiTochiParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEISEI_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEISEI_TOCHI_START

# Register
ApiRegistry.register(API_KEY_KEISEI_MANSION_START, ParseKeiseiMansionStartAsync)
ApiRegistry.register(API_KEY_KEISEI_MANSION_DETAIL, ParseKeiseiMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_KEISEI_KODATE_START, ParseKeiseiKodateStartAsync)
ApiRegistry.register(API_KEY_KEISEI_KODATE_DETAIL, ParseKeiseiKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_KEISEI_TOCHI_START, ParseKeiseiTochiStartAsync)
ApiRegistry.register(API_KEY_KEISEI_TOCHI_DETAIL, ParseKeiseiTochiDetailFuncAsync)
