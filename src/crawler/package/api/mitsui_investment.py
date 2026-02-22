
import os
import asyncio
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase, \
    API_KEY_MITSUI_INVEST_KODATE_START, API_KEY_MITSUI_INVEST_KODATE_AREA, API_KEY_MITSUI_INVEST_KODATE_LIST, API_KEY_MITSUI_INVEST_KODATE_DETAIL, \
    API_KEY_MITSUI_INVEST_KODATE_START_GCP, API_KEY_MITSUI_INVEST_KODATE_AREA_GCP, API_KEY_MITSUI_INVEST_KODATE_LIST_GCP, API_KEY_MITSUI_INVEST_KODATE_DETAIL_GCP, \
    API_KEY_MITSUI_INVEST_APARTMENT_START, API_KEY_MITSUI_INVEST_APARTMENT_AREA, API_KEY_MITSUI_INVEST_APARTMENT_LIST, API_KEY_MITSUI_INVEST_APARTMENT_DETAIL, \
    API_KEY_MITSUI_INVEST_APARTMENT_START_GCP, API_KEY_MITSUI_INVEST_APARTMENT_AREA_GCP, API_KEY_MITSUI_INVEST_APARTMENT_LIST_GCP, API_KEY_MITSUI_INVEST_APARTMENT_DETAIL_GCP

from package.parser.mitsuiParser import MitsuiInvestmentKodateParser, MitsuiInvestmentApartmentParser
from package.api.registry import ApiRegistry

DEFAULT_PARALLEL_LIMIT = 1
DETAIL_PARALLEL_LIMIT = 1

class ParseMitsuiInvestListFuncAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getNextPageParserFunc(self):
        return self.parser.getPropertyListNextPageUrl
    
    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 360

class ParseMitsuiInvestAreaFuncAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parseAreaPage
    
    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

class ParseMitsuiInvestDetailFuncAsyncBase(ParseDetailPageAsyncBase):
    def _getLocalPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 60
    
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""

class ParseMitsuiInvestStartAsyncBase(ParseMiddlePageAsyncBase):
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DEFAULT_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 2400

# ==============================================================================
#  KODATE (戸建て賃貸)
# ==============================================================================

class ParseMitsuiInvestKodateDetailFuncAsync(ParseMitsuiInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentKodateParser("")

class ParseMitsuiInvestKodateListFuncAsync(ParseMitsuiInvestListFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentKodateParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_KODATE_LIST_GCP
        return API_KEY_MITSUI_INVEST_KODATE_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_KODATE_DETAIL_GCP
        return API_KEY_MITSUI_INVEST_KODATE_DETAIL

class ParseMitsuiInvestKodateAreaFuncAsync(ParseMitsuiInvestAreaFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentKodateParser("")
    
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_KODATE_LIST_GCP
        return API_KEY_MITSUI_INVEST_KODATE_LIST

class ParseMitsuiInvestKodateStartAsync(ParseMitsuiInvestStartAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentKodateParser("")
    
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_KODATE_AREA_GCP
        return API_KEY_MITSUI_INVEST_KODATE_AREA

# ==============================================================================
#  APARTMENT (アパート)
# ==============================================================================

class ParseMitsuiInvestApartmentDetailFuncAsync(ParseMitsuiInvestDetailFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentApartmentParser("")

class ParseMitsuiInvestApartmentListFuncAsync(ParseMitsuiInvestListFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentApartmentParser("")
    
    def _getNextPageApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_APARTMENT_LIST_GCP
        return API_KEY_MITSUI_INVEST_APARTMENT_LIST

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_APARTMENT_DETAIL_GCP
        return API_KEY_MITSUI_INVEST_APARTMENT_DETAIL

class ParseMitsuiInvestApartmentAreaFuncAsync(ParseMitsuiInvestAreaFuncAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentApartmentParser("")
    
    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_APARTMENT_LIST_GCP
        return API_KEY_MITSUI_INVEST_APARTMENT_LIST

class ParseMitsuiInvestApartmentStartAsync(ParseMitsuiInvestStartAsyncBase):
    def _generateParser(self):
        return MitsuiInvestmentApartmentParser("")

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_INVEST_APARTMENT_AREA_GCP
        return API_KEY_MITSUI_INVEST_APARTMENT_AREA

# ==============================================================================
#  REGISTRY
# ==============================================================================

# Kodate
ApiRegistry.register(API_KEY_MITSUI_INVEST_KODATE_START, ParseMitsuiInvestKodateStartAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_KODATE_AREA, ParseMitsuiInvestKodateAreaFuncAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_KODATE_LIST, ParseMitsuiInvestKodateListFuncAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_KODATE_DETAIL, ParseMitsuiInvestKodateDetailFuncAsync)

# Apartment
ApiRegistry.register(API_KEY_MITSUI_INVEST_APARTMENT_START, ParseMitsuiInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_APARTMENT_AREA, ParseMitsuiInvestApartmentAreaFuncAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_APARTMENT_LIST, ParseMitsuiInvestApartmentListFuncAsync)
ApiRegistry.register(API_KEY_MITSUI_INVEST_APARTMENT_DETAIL, ParseMitsuiInvestApartmentDetailFuncAsync)
