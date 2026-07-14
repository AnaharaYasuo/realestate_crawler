# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_SEIBU_MANSION_START, API_KEY_SEIBU_MANSION_DETAIL,
    API_KEY_SEIBU_KODATE_START, API_KEY_SEIBU_KODATE_DETAIL,
    API_KEY_SEIBU_TOCHI_START, API_KEY_SEIBU_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.seibuParser import (
    SeibuMansionParser, SeibuKodateParser, SeibuTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseSeibuMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SeibuMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSeibuMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SeibuMansionParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SEIBU_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SEIBU_MANSION_START

# Kodate
class ParseSeibuKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SeibuKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSeibuKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SeibuKodateParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SEIBU_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SEIBU_KODATE_START

# Tochi
class ParseSeibuTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return SeibuTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseSeibuTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return SeibuTochiParser()
    def _getParserFunc(self): return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self): return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return 1
    def _getCloudPararellLimit(self): return 1
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_SEIBU_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_SEIBU_TOCHI_START

# Register
ApiRegistry.register(API_KEY_SEIBU_MANSION_START, ParseSeibuMansionStartAsync)
ApiRegistry.register(API_KEY_SEIBU_MANSION_DETAIL, ParseSeibuMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_SEIBU_KODATE_START, ParseSeibuKodateStartAsync)
ApiRegistry.register(API_KEY_SEIBU_KODATE_DETAIL, ParseSeibuKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_SEIBU_TOCHI_START, ParseSeibuTochiStartAsync)
ApiRegistry.register(API_KEY_SEIBU_TOCHI_DETAIL, ParseSeibuTochiDetailFuncAsync)
