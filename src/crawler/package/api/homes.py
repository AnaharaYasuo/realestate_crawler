# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_HOMES_INVEST_APARTMENT_START, API_KEY_HOMES_INVEST_APARTMENT_DETAIL,
    API_KEY_HOMES_MANSION_START, API_KEY_HOMES_MANSION_DETAIL,
    API_KEY_HOMES_KODATE_START, API_KEY_HOMES_KODATE_DETAIL,
    API_KEY_HOMES_TOCHI_START, API_KEY_HOMES_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.homesParser import (
    HomesKodateParser, HomesInvestmentApartmentParser, HomesTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseHomesMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HomesInvestmentApartmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHomesMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HomesInvestmentApartmentParser()

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
        return API_KEY_HOMES_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HOMES_MANSION_START

# --- Kodate ---
class ParseHomesKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HomesKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHomesKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HomesKodateParser()

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
        return API_KEY_HOMES_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HOMES_KODATE_START

# --- Investment ---
class ParseHomesInvestApartmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HomesInvestmentApartmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHomesInvestApartmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HomesInvestmentApartmentParser()

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
        return API_KEY_HOMES_INVEST_APARTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HOMES_INVEST_APARTMENT_START


# --- Tochi ---
class ParseHomesTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HomesTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHomesTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HomesTochiParser()

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
        return API_KEY_HOMES_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HOMES_TOCHI_START


# Registry
ApiRegistry.register(API_KEY_HOMES_MANSION_START, ParseHomesMansionStartAsync)
ApiRegistry.register(API_KEY_HOMES_MANSION_DETAIL, ParseHomesMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_HOMES_KODATE_START, ParseHomesKodateStartAsync)
ApiRegistry.register(API_KEY_HOMES_KODATE_DETAIL, ParseHomesKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_HOMES_INVEST_APARTMENT_START, ParseHomesInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_HOMES_INVEST_APARTMENT_DETAIL, ParseHomesInvestApartmentDetailFuncAsync)

ApiRegistry.register(API_KEY_HOMES_TOCHI_START, ParseHomesTochiStartAsync)
ApiRegistry.register(API_KEY_HOMES_TOCHI_DETAIL, ParseHomesTochiDetailFuncAsync)

