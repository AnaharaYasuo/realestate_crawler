# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_ODAKYU_MANSION_START, API_KEY_ODAKYU_MANSION_DETAIL,
    API_KEY_ODAKYU_KODATE_START, API_KEY_ODAKYU_KODATE_DETAIL,
    API_KEY_ODAKYU_TOCHI_START, API_KEY_ODAKYU_TOCHI_DETAIL,
    API_KEY_ODAKYU_INVESTMENT_START, API_KEY_ODAKYU_INVESTMENT_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.odakyuParser import (
    OdakyuMansionParser, OdakyuKodateParser, OdakyuTochiParser, OdakyuInvestmentParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# Mansion
class ParseOdakyuMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return OdakyuMansionParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseOdakyuMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return OdakyuMansionParser()
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
        return API_KEY_ODAKYU_MANSION_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_ODAKYU_MANSION_START

# Kodate
class ParseOdakyuKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return OdakyuKodateParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseOdakyuKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return OdakyuKodateParser()
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
        return API_KEY_ODAKYU_KODATE_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_ODAKYU_KODATE_START

# Tochi
class ParseOdakyuTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return OdakyuTochiParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseOdakyuTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return OdakyuTochiParser()
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
        return API_KEY_ODAKYU_TOCHI_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_ODAKYU_TOCHI_START

# Investment
class ParseOdakyuInvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return OdakyuInvestmentParser()
    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT
    def _getTimeOutSecond(self):
        return 60
    def _getApiKey(self):
        return ""

class ParseOdakyuInvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return OdakyuInvestmentParser()
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
        return API_KEY_ODAKYU_INVESTMENT_DETAIL
    def _getNextPageApiKey(self):
        return API_KEY_ODAKYU_INVESTMENT_START

# Registry
ApiRegistry.register(API_KEY_ODAKYU_MANSION_START, ParseOdakyuMansionStartAsync)
ApiRegistry.register(API_KEY_ODAKYU_MANSION_DETAIL, ParseOdakyuMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_ODAKYU_KODATE_START, ParseOdakyuKodateStartAsync)
ApiRegistry.register(API_KEY_ODAKYU_KODATE_DETAIL, ParseOdakyuKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_ODAKYU_TOCHI_START, ParseOdakyuTochiStartAsync)
ApiRegistry.register(API_KEY_ODAKYU_TOCHI_DETAIL, ParseOdakyuTochiDetailFuncAsync)
ApiRegistry.register(API_KEY_ODAKYU_INVESTMENT_START, ParseOdakyuInvestmentStartAsync)
ApiRegistry.register(API_KEY_ODAKYU_INVESTMENT_DETAIL, ParseOdakyuInvestmentDetailFuncAsync)

