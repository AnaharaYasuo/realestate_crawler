# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_SUMAI1_MANSION_START, API_KEY_SUMAI1_MANSION_DETAIL,
    API_KEY_SUMAI1_KODATE_START, API_KEY_SUMAI1_KODATE_DETAIL,
    API_KEY_SUMAI1_TOCHI_START, API_KEY_SUMAI1_TOCHI_DETAIL,
    API_KEY_SUMAI1_INVESTMENT_START, API_KEY_SUMAI1_INVESTMENT_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.sumai1Parser import (
    Sumai1MansionParser, Sumai1KodateParser, Sumai1TochiParser, Sumai1InvestmentParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseSumai1MansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return Sumai1MansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumai1MansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return Sumai1MansionParser()

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
        return API_KEY_SUMAI1_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMAI1_MANSION_START


# --- Kodate ---
class ParseSumai1KodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return Sumai1KodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumai1KodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return Sumai1KodateParser()

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
        return API_KEY_SUMAI1_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMAI1_KODATE_START


# --- Tochi ---
class ParseSumai1TochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return Sumai1TochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumai1TochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return Sumai1TochiParser()

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
        return API_KEY_SUMAI1_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMAI1_TOCHI_START


# --- Investment ---
class ParseSumai1InvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return Sumai1InvestmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumai1InvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return Sumai1InvestmentParser()

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
        return API_KEY_SUMAI1_INVESTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMAI1_INVESTMENT_START


# Registry
ApiRegistry.register(API_KEY_SUMAI1_MANSION_START, ParseSumai1MansionStartAsync)
ApiRegistry.register(API_KEY_SUMAI1_MANSION_DETAIL, ParseSumai1MansionDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMAI1_KODATE_START, ParseSumai1KodateStartAsync)
ApiRegistry.register(API_KEY_SUMAI1_KODATE_DETAIL, ParseSumai1KodateDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMAI1_TOCHI_START, ParseSumai1TochiStartAsync)
ApiRegistry.register(API_KEY_SUMAI1_TOCHI_DETAIL, ParseSumai1TochiDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMAI1_INVESTMENT_START, ParseSumai1InvestmentStartAsync)
ApiRegistry.register(API_KEY_SUMAI1_INVESTMENT_DETAIL, ParseSumai1InvestmentDetailFuncAsync)

