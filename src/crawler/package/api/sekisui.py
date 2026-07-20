# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_SEKISUI_MANSION_START, API_KEY_SEKISUI_MANSION_DETAIL,
    API_KEY_SEKISUI_KODATE_START, API_KEY_SEKISUI_KODATE_DETAIL,
    API_KEY_SEKISUI_TOCHI_START, API_KEY_SEKISUI_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.sekisuiParser import (
    SekisuiMansionParser, SekisuiKodateParser, SekisuiTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseSekisuiMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SekisuiMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSekisuiMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SekisuiMansionParser()

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
        return API_KEY_SEKISUI_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SEKISUI_MANSION_START


# --- Kodate ---
class ParseSekisuiKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SekisuiKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSekisuiKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SekisuiKodateParser()

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
        return API_KEY_SEKISUI_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SEKISUI_KODATE_START


# --- Tochi ---
class ParseSekisuiTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SekisuiTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSekisuiTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SekisuiTochiParser()

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
        return API_KEY_SEKISUI_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SEKISUI_TOCHI_START


# Registry
ApiRegistry.register(API_KEY_SEKISUI_MANSION_START, ParseSekisuiMansionStartAsync)
ApiRegistry.register(API_KEY_SEKISUI_MANSION_DETAIL, ParseSekisuiMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_SEKISUI_KODATE_START, ParseSekisuiKodateStartAsync)
ApiRegistry.register(API_KEY_SEKISUI_KODATE_DETAIL, ParseSekisuiKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_SEKISUI_TOCHI_START, ParseSekisuiTochiStartAsync)
ApiRegistry.register(API_KEY_SEKISUI_TOCHI_DETAIL, ParseSekisuiTochiDetailFuncAsync)
