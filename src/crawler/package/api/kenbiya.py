from package.api.api import (
    API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL,
    API_KEY_KENBIYA_INVEST_APARTMENT_START,
    API_KEY_KENBIYA_INVEST_BUILDING_DETAIL,
    API_KEY_KENBIYA_INVEST_BUILDING_START,
    API_KEY_KENBIYA_KODATE_DETAIL,
    API_KEY_KENBIYA_KODATE_START,
    API_KEY_KENBIYA_MANSION_DETAIL,
    API_KEY_KENBIYA_MANSION_START,
    API_KEY_KENBIYA_TOCHI_DETAIL,
    API_KEY_KENBIYA_TOCHI_START,
    ParseDetailPageAsyncBase,
    ParseMiddlePageAsyncBase,
)
from package.api.registry import ApiRegistry
from package.parser.kenbiyaParser import (
    KenbiyaInvestmentApartmentParser,
    KenbiyaInvestmentBuildingParser,
    KenbiyaKodateParser,
    KenbiyaMansionParser,
    KenbiyaTochiParser,
)

DETAIL_PARALLEL_LIMIT = 1
MIDDLE_PARALLEL_LIMIT = 1

# Mansion (/pp1/)
class ParseKenbiyaMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaMansionParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKenbiyaMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaMansionParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_MANSION_START

# Kodate (/pp8/)
class ParseKenbiyaKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKenbiyaKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaKodateParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_KODATE_START

# Tochi (/pp5/)
class ParseKenbiyaTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKenbiyaTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaTochiParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_TOCHI_START

# Investment Apartment (/pp2/)
class ParseKenbiyaInvestApartmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentApartmentParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKenbiyaInvestApartmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentApartmentParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_INVEST_APARTMENT_START

# Investment Building (/pp3/, /pp4/)
class ParseKenbiyaInvestBuildingDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentBuildingParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

class ParseKenbiyaInvestBuildingStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentBuildingParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_INVEST_BUILDING_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_INVEST_BUILDING_START

# Register
ApiRegistry.register(API_KEY_KENBIYA_MANSION_START, ParseKenbiyaMansionStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_MANSION_DETAIL, ParseKenbiyaMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_KODATE_START, ParseKenbiyaKodateStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_KODATE_DETAIL, ParseKenbiyaKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_TOCHI_START, ParseKenbiyaTochiStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_TOCHI_DETAIL, ParseKenbiyaTochiDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_APARTMENT_START, ParseKenbiyaInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL, ParseKenbiyaInvestApartmentDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_BUILDING_START, ParseKenbiyaInvestBuildingStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_BUILDING_DETAIL, ParseKenbiyaInvestBuildingDetailFuncAsync)
