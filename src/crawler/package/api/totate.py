# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_TOTATE_MANSION_START, API_KEY_TOTATE_MANSION_DETAIL,
    API_KEY_TOTATE_KODATE_START, API_KEY_TOTATE_KODATE_DETAIL,
    API_KEY_TOTATE_TOCHI_START, API_KEY_TOTATE_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.totateParser import (
    TotateMansionParser, TotateKodateParser, TotateTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseTotateMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TotateMansionParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseTotateMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return TotateMansionParser()
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
        return API_KEY_TOTATE_MANSION_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_TOTATE_MANSION_START

# Kodate
class ParseTotateKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TotateKodateParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseTotateKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return TotateKodateParser()
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
        return API_KEY_TOTATE_KODATE_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_TOTATE_KODATE_START

# Tochi
class ParseTotateTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TotateTochiParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseTotateTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return TotateTochiParser()
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
        return API_KEY_TOTATE_TOCHI_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_TOTATE_TOCHI_START

# Registry
ApiRegistry.register(API_KEY_TOTATE_MANSION_START, ParseTotateMansionStartAsync)
ApiRegistry.register(API_KEY_TOTATE_MANSION_DETAIL, ParseTotateMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_TOTATE_KODATE_START, ParseTotateKodateStartAsync)
ApiRegistry.register(API_KEY_TOTATE_KODATE_DETAIL, ParseTotateKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_TOTATE_TOCHI_START, ParseTotateTochiStartAsync)
ApiRegistry.register(API_KEY_TOTATE_TOCHI_DETAIL, ParseTotateTochiDetailFuncAsync)
