# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_IETAN_MANSION_START, API_KEY_IETAN_MANSION_DETAIL,
    API_KEY_IETAN_KODATE_START, API_KEY_IETAN_KODATE_DETAIL,
    API_KEY_IETAN_TOCHI_START, API_KEY_IETAN_TOCHI_DETAIL,
    API_KEY_HASEKO_MANSION_START, API_KEY_HASEKO_MANSION_DETAIL,
    API_KEY_ADCAST_KODATE_START, API_KEY_ADCAST_KODATE_DETAIL,
    API_KEY_ADCAST_TOCHI_START, API_KEY_ADCAST_TOCHI_DETAIL,
    API_KEY_TOHO_MANSION_START, API_KEY_TOHO_MANSION_DETAIL,
    API_KEY_TOHO_KODATE_START, API_KEY_TOHO_KODATE_DETAIL,
    API_KEY_TOHO_TOCHI_START, API_KEY_TOHO_TOCHI_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.ietanParser import IetanMansionParser, IetanKodateParser, IetanTochiParser
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.adcastParser import AdCastKodateParser, AdCastTochiParser
from package.parser.tohoParser import TohoMansionParser, TohoKodateParser, TohoTochiParser

DETAIL_PARALLEL_LIMIT = 3

# --- Ietan ---
class ParseIetanMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return IetanMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseIetanKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return IetanKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseIetanTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return IetanTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

# --- Haseko ---
class ParseHasekoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return HasekoMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

# --- AdCast ---
class ParseAdCastKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AdCastKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseAdCastTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return AdCastTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

# --- Toho ---
class ParseTohoMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TohoMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseTohoKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TohoKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseTohoTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return TohoTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""
