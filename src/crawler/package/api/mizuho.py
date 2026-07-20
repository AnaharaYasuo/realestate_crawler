# -*- coding: utf-8 -*-
from package.api.api import (
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
# api.py からキーを読み込む
from package.api.api import (
    API_KEY_MIZUHO_MANSION_START, API_KEY_MIZUHO_MANSION_DETAIL,
    API_KEY_MIZUHO_KODATE_START, API_KEY_MIZUHO_KODATE_DETAIL,
    API_KEY_MIZUHO_TOCHI_START, API_KEY_MIZUHO_TOCHI_DETAIL,
    API_KEY_MIZUHO_INVESTMENT_START, API_KEY_MIZUHO_INVESTMENT_DETAIL
)
from package.parser.mizuhoParser import (
    MizuhoMansionParser, MizuhoKodateParser, MizuhoTochiParser, MizuhoInvestmentParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseMizuhoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MizuhoMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMizuhoMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return MizuhoMansionParser()

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
        return API_KEY_MIZUHO_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MIZUHO_MANSION_START


# --- Kodate ---
class ParseMizuhoKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MizuhoKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMizuhoKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return MizuhoKodateParser()

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
        return API_KEY_MIZUHO_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MIZUHO_KODATE_START


# --- Tochi ---
class ParseMizuhoTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MizuhoTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMizuhoTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return MizuhoTochiParser()

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
        return API_KEY_MIZUHO_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MIZUHO_TOCHI_START


# --- Investment ---
class ParseMizuhoInvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MizuhoInvestmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseMizuhoInvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return MizuhoInvestmentParser()

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
        return API_KEY_MIZUHO_INVESTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_MIZUHO_INVESTMENT_START


# Registry
ApiRegistry.register(API_KEY_MIZUHO_MANSION_START, ParseMizuhoMansionStartAsync)
ApiRegistry.register(API_KEY_MIZUHO_MANSION_DETAIL, ParseMizuhoMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_MIZUHO_KODATE_START, ParseMizuhoKodateStartAsync)
ApiRegistry.register(API_KEY_MIZUHO_KODATE_DETAIL, ParseMizuhoKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_MIZUHO_TOCHI_START, ParseMizuhoTochiStartAsync)
ApiRegistry.register(API_KEY_MIZUHO_TOCHI_DETAIL, ParseMizuhoTochiDetailFuncAsync)

ApiRegistry.register(API_KEY_MIZUHO_INVESTMENT_START, ParseMizuhoInvestmentStartAsync)
ApiRegistry.register(API_KEY_MIZUHO_INVESTMENT_DETAIL, ParseMizuhoInvestmentDetailFuncAsync)

