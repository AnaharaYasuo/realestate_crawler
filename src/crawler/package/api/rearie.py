# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_REARIE_MANSION_START, API_KEY_REARIE_MANSION_DETAIL,
    API_KEY_REARIE_KODATE_START, API_KEY_REARIE_KODATE_DETAIL,
    API_KEY_REARIE_TOCHI_START, API_KEY_REARIE_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.rearieParser import (
    RearieMansionParser, RearieKodateParser, RearieTochiParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseRearieMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return RearieMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseRearieMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return RearieMansionParser()

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
        return API_KEY_REARIE_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_REARIE_MANSION_START

# --- Kodate ---
class ParseRearieKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return RearieKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseRearieKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return RearieKodateParser()

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
        return API_KEY_REARIE_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_REARIE_KODATE_START

# --- Tochi ---
class ParseRearieTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return RearieTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseRearieTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return RearieTochiParser()

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
        return API_KEY_REARIE_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_REARIE_TOCHI_START


# Registry への登録
ApiRegistry.register(API_KEY_REARIE_MANSION_START, ParseRearieMansionStartAsync)
ApiRegistry.register(API_KEY_REARIE_MANSION_DETAIL, ParseRearieMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_REARIE_KODATE_START, ParseRearieKodateStartAsync)
ApiRegistry.register(API_KEY_REARIE_KODATE_DETAIL, ParseRearieKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_REARIE_TOCHI_START, ParseRearieTochiStartAsync)
ApiRegistry.register(API_KEY_REARIE_TOCHI_DETAIL, ParseRearieTochiDetailFuncAsync)
