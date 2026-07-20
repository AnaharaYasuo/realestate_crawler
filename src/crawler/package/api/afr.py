# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_AFR_MANSION_START, API_KEY_AFR_MANSION_DETAIL,
    API_KEY_AFR_KODATE_START, API_KEY_AFR_KODATE_DETAIL,
    API_KEY_AFR_TOCHI_START, API_KEY_AFR_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.afrParser import (
    AfrMansionParser, AfrKodateParser, AfrTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseAfrMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AfrMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAfrMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AfrMansionParser()

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
        return API_KEY_AFR_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_AFR_MANSION_START


# --- Kodate ---
class ParseAfrKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AfrKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAfrKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AfrKodateParser()

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
        return API_KEY_AFR_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_AFR_KODATE_START


# --- Tochi ---
class ParseAfrTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AfrTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseAfrTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return AfrTochiParser()

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
        return API_KEY_AFR_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_AFR_TOCHI_START


# Registry
ApiRegistry.register(API_KEY_AFR_MANSION_START, ParseAfrMansionStartAsync)
ApiRegistry.register(API_KEY_AFR_MANSION_DETAIL, ParseAfrMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_AFR_KODATE_START, ParseAfrKodateStartAsync)
ApiRegistry.register(API_KEY_AFR_KODATE_DETAIL, ParseAfrKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_AFR_TOCHI_START, ParseAfrTochiStartAsync)
ApiRegistry.register(API_KEY_AFR_TOCHI_DETAIL, ParseAfrTochiDetailFuncAsync)
