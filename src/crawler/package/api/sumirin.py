# -*- coding: utf-8 -*-
import os
import logging
from package.api.api import (
    API_KEY_SUMIRIN_MANSION_START, API_KEY_SUMIRIN_MANSION_DETAIL,
    API_KEY_SUMIRIN_KODATE_START, API_KEY_SUMIRIN_KODATE_DETAIL,
    API_KEY_SUMIRIN_TOCHI_START, API_KEY_SUMIRIN_TOCHI_DETAIL,
    API_KEY_SUMIRIN_INVESTMENT_START, API_KEY_SUMIRIN_INVESTMENT_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.sumirinParser import (
    SumirinMansionParser, SumirinKodateParser, SumirinTochiParser, SumirinInvestmentParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseSumirinMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SumirinMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumirinMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SumirinMansionParser()

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
        return API_KEY_SUMIRIN_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMIRIN_MANSION_START


# --- Kodate ---
class ParseSumirinKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SumirinKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumirinKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SumirinKodateParser()

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
        return API_KEY_SUMIRIN_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMIRIN_KODATE_START


# --- Tochi ---
class ParseSumirinTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SumirinTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumirinTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SumirinTochiParser()

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
        return API_KEY_SUMIRIN_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMIRIN_TOCHI_START


# --- Investment ---
class ParseSumirinInvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SumirinInvestmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSumirinInvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SumirinInvestmentParser()

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
        return API_KEY_SUMIRIN_INVESTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SUMIRIN_INVESTMENT_START


# Registry
ApiRegistry.register(API_KEY_SUMIRIN_MANSION_START, ParseSumirinMansionStartAsync)
ApiRegistry.register(API_KEY_SUMIRIN_MANSION_DETAIL, ParseSumirinMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMIRIN_KODATE_START, ParseSumirinKodateStartAsync)
ApiRegistry.register(API_KEY_SUMIRIN_KODATE_DETAIL, ParseSumirinKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMIRIN_TOCHI_START, ParseSumirinTochiStartAsync)
ApiRegistry.register(API_KEY_SUMIRIN_TOCHI_DETAIL, ParseSumirinTochiDetailFuncAsync)

ApiRegistry.register(API_KEY_SUMIRIN_INVESTMENT_START, ParseSumirinInvestmentStartAsync)
ApiRegistry.register(API_KEY_SUMIRIN_INVESTMENT_DETAIL, ParseSumirinInvestmentDetailFuncAsync)
