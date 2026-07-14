# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_KEIKYU_MANSION_START, API_KEY_KEIKYU_MANSION_DETAIL,
    API_KEY_KEIKYU_KODATE_START, API_KEY_KEIKYU_KODATE_DETAIL,
    API_KEY_KEIKYU_TOCHI_START, API_KEY_KEIKYU_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.keikyuParser import (
    KeikyuMansionParser, KeikyuKodateParser, KeikyuTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseKeikyuMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeikyuMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeikyuMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeikyuMansionParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEIKYU_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEIKYU_MANSION_START

# Kodate
class ParseKeikyuKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeikyuKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeikyuStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeikyuKodateParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEIKYU_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEIKYU_KODATE_START

# Tochi
class ParseKeikyuTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KeikyuTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKeikyuTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KeikyuTochiParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KEIKYU_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KEIKYU_TOCHI_START

# Register
ApiRegistry.register(API_KEY_KEIKYU_MANSION_START, ParseKeikyuMansionStartAsync)
ApiRegistry.register(API_KEY_KEIKYU_MANSION_DETAIL, ParseKeikyuMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_KEIKYU_KODATE_START, ParseKeikyuStartAsync)
ApiRegistry.register(API_KEY_KEIKYU_KODATE_DETAIL, ParseKeikyuKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_KEIKYU_TOCHI_START, ParseKeikyuTochiStartAsync)
ApiRegistry.register(API_KEY_KEIKYU_TOCHI_DETAIL, ParseKeikyuTochiDetailFuncAsync)
