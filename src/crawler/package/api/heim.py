# -*- coding: utf-8 -*-
import os
import logging
from package.api.api import (
    API_KEY_HEIM_MANSION_START, API_KEY_HEIM_MANSION_DETAIL,
    API_KEY_HEIM_KODATE_START, API_KEY_HEIM_KODATE_DETAIL,
    API_KEY_HEIM_TOCHI_START, API_KEY_HEIM_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.heimParser import (
    HeimMansionParser, HeimKodateParser, HeimTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseHeimMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HeimMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHeimMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HeimMansionParser()

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
        return API_KEY_HEIM_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HEIM_MANSION_START

# --- Kodate ---
class ParseHeimKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HeimKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHeimKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HeimKodateParser()

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
        return API_KEY_HEIM_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HEIM_KODATE_START

# --- Tochi ---
class ParseHeimTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HeimTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseHeimTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return HeimTochiParser()

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
        return API_KEY_HEIM_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_HEIM_TOCHI_START


# Registry への登録
ApiRegistry.register(API_KEY_HEIM_MANSION_START, ParseHeimMansionStartAsync)
ApiRegistry.register(API_KEY_HEIM_MANSION_DETAIL, ParseHeimMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_HEIM_KODATE_START, ParseHeimKodateStartAsync)
ApiRegistry.register(API_KEY_HEIM_KODATE_DETAIL, ParseHeimKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_HEIM_TOCHI_START, ParseHeimTochiStartAsync)
ApiRegistry.register(API_KEY_HEIM_TOCHI_DETAIL, ParseHeimTochiDetailFuncAsync)
