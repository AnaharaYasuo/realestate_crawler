from package.api.api import (
    API_KEY_REGUIDE_INVESTMENT_DETAIL,
    API_KEY_REGUIDE_INVESTMENT_START,
    ParseDetailPageAsyncBase,
    ParseMiddlePageAsyncBase,
)
from package.api.registry import ApiRegistry
from package.parser.reguideParser import ReguideInvestmentParser

DETAIL_PARALLEL_LIMIT = 3
MIDDLE_PARALLEL_LIMIT = 3


class ParseReguideInvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return ReguideInvestmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""


class ParseReguideInvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return ReguideInvestmentParser()

    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getNextPageParserFunc(self):
        return self.parser.parseNextPage

    def _isBsMiddlePage(self):
        return True

    def _getLocalPararellLimit(self):
        return MIDDLE_PARALLEL_LIMIT

    def _getCloudPararellLimit(self):
        return MIDDLE_PARALLEL_LIMIT

    def _getTimeOutSecond(self):
        return 600

    def _getApiKey(self):
        return API_KEY_REGUIDE_INVESTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_REGUIDE_INVESTMENT_START


# Registry
ApiRegistry.register(API_KEY_REGUIDE_INVESTMENT_START, ParseReguideInvestmentStartAsync)
ApiRegistry.register(API_KEY_REGUIDE_INVESTMENT_DETAIL, ParseReguideInvestmentDetailFuncAsync)
