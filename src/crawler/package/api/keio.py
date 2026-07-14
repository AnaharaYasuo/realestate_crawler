# -*- coding: utf-8 -*-
import os
import logging
from package.api.api import (
    API_KEY_KEIO_MANSION_START, API_KEY_KEIO_MANSION_DETAIL,
    API_KEY_KEIO_KODATE_START, API_KEY_KEIO_KODATE_DETAIL,
    API_KEY_KEIO_TOCHI_START, API_KEY_KEIO_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.keioParser import (
    KeioMansionParser, KeioKodateParser, KeioTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseKeioMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return KeioMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseKeioMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return KeioMansionParser()

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
        return API_KEY_KEIO_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_KEIO_MANSION_START

# --- Kodate ---
class ParseKeioKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return KeioKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseKeioKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return KeioKodateParser()

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
        return API_KEY_KEIO_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_KEIO_KODATE_START

# --- Tochi ---
class ParseKeioTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return KeioTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseKeioTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return KeioTochiParser()

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
        return API_KEY_KEIO_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_KEIO_TOCHI_START


# Registry への登録
ApiRegistry.register(API_KEY_KEIO_MANSION_START, ParseKeioMansionStartAsync)
ApiRegistry.register(API_KEY_KEIO_MANSION_DETAIL, ParseKeioMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_KEIO_KODATE_START, ParseKeioKodateStartAsync)
ApiRegistry.register(API_KEY_KEIO_KODATE_DETAIL, ParseKeioKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_KEIO_TOCHI_START, ParseKeioTochiStartAsync)
ApiRegistry.register(API_KEY_KEIO_TOCHI_DETAIL, ParseKeioTochiDetailFuncAsync)
