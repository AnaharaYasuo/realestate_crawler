# -*- coding: utf-8 -*-
import os
import logging
from package.api.api import (
    API_KEY_ATHOME_INVEST_APARTMENT_START, API_KEY_ATHOME_INVEST_APARTMENT_DETAIL,
    API_KEY_ATHOME_MANSION_START, API_KEY_ATHOME_MANSION_DETAIL,
    API_KEY_ATHOME_KODATE_START, API_KEY_ATHOME_KODATE_DETAIL,
    API_KEY_ATHOME_TOCHI_START, API_KEY_ATHOME_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.athomeParser import (
    AthomeMansionParser, AthomeKodateParser, AthomeInvestmentApartmentParser, AthomeTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseAthomeMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AthomeMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAthomeMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AthomeMansionParser()

    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')

    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')

    def _isBsMiddlePage(self):
        return False

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        return API_KEY_ATHOME_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_ATHOME_MANSION_START

# --- Kodate ---
class ParseAthomeKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AthomeKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAthomeKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AthomeKodateParser()

    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')

    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')

    def _isBsMiddlePage(self):
        return False

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        return API_KEY_ATHOME_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_ATHOME_KODATE_START

# --- Investment ---
class ParseAthomeInvestApartmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AthomeInvestmentApartmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAthomeInvestApartmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AthomeInvestmentApartmentParser()

    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')

    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')

    def _isBsMiddlePage(self):
        return False

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        return API_KEY_ATHOME_INVEST_APARTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_ATHOME_INVEST_APARTMENT_START


# --- Tochi ---
class ParseAthomeTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AthomeTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAthomeTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AthomeTochiParser()

    def _getParserFunc(self):
        return getattr(self.parser, 'parseRootPage')

    def _getNextPageParserFunc(self):
        return getattr(self.parser, 'parseNextPage')

    def _isBsMiddlePage(self):
        return False

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        return API_KEY_ATHOME_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_ATHOME_TOCHI_START


# Registry
ApiRegistry.register(API_KEY_ATHOME_MANSION_START, ParseAthomeMansionStartAsync)
ApiRegistry.register(API_KEY_ATHOME_MANSION_DETAIL, ParseAthomeMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_ATHOME_KODATE_START, ParseAthomeKodateStartAsync)
ApiRegistry.register(API_KEY_ATHOME_KODATE_DETAIL, ParseAthomeKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_ATHOME_INVEST_APARTMENT_START, ParseAthomeInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_ATHOME_INVEST_APARTMENT_DETAIL, ParseAthomeInvestApartmentDetailFuncAsync)

ApiRegistry.register(API_KEY_ATHOME_TOCHI_START, ParseAthomeTochiStartAsync)
ApiRegistry.register(API_KEY_ATHOME_TOCHI_DETAIL, ParseAthomeTochiDetailFuncAsync)

