# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_DAIWA_MANSION_START, API_KEY_DAIWA_MANSION_DETAIL,
    API_KEY_DAIWA_KODATE_START, API_KEY_DAIWA_KODATE_DETAIL,
    API_KEY_DAIWA_TOCHI_START, API_KEY_DAIWA_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.daiwaParser import (
    DaiwaMansionParser, DaiwaKodateParser, DaiwaTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseDaiwaMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return DaiwaMansionParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseDaiwaMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return DaiwaMansionParser()
    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self):
        return True
    def _getLocalPararellLimit(self):
        return 1
    def _getCloudPararellLimit(self):
        return 1
    def _getTimeOutSecond(self):
        return 600
    def _getApiKey(self):
        return API_KEY_DAIWA_MANSION_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_DAIWA_MANSION_START

# Kodate
class ParseDaiwaKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return DaiwaKodateParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseDaiwaKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return DaiwaKodateParser()
    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self):
        return True
    def _getLocalPararellLimit(self):
        return 1
    def _getCloudPararellLimit(self):
        return 1
    def _getTimeOutSecond(self):
        return 600
    def _getApiKey(self):
        return API_KEY_DAIWA_KODATE_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_DAIWA_KODATE_START

# Tochi
class ParseDaiwaTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return DaiwaTochiParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseDaiwaTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return DaiwaTochiParser()
    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')
    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')
    def _isBsMiddlePage(self):
        return True
    def _getLocalPararellLimit(self):
        return 1
    def _getCloudPararellLimit(self):
        return 1
    def _getTimeOutSecond(self):
        return 600
    def _getApiKey(self):
        return API_KEY_DAIWA_TOCHI_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_DAIWA_TOCHI_START

# Registry
ApiRegistry.register(API_KEY_DAIWA_MANSION_START, ParseDaiwaMansionStartAsync)
ApiRegistry.register(API_KEY_DAIWA_MANSION_DETAIL, ParseDaiwaMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_DAIWA_KODATE_START, ParseDaiwaKodateStartAsync)
ApiRegistry.register(API_KEY_DAIWA_KODATE_DETAIL, ParseDaiwaKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_DAIWA_TOCHI_START, ParseDaiwaTochiStartAsync)
ApiRegistry.register(API_KEY_DAIWA_TOCHI_DETAIL, ParseDaiwaTochiDetailFuncAsync)
