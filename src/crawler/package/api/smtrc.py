# -*- coding: utf-8 -*-
from package.api.api import (
    API_KEY_SMTRC_MANSION_START, API_KEY_SMTRC_MANSION_DETAIL,
    API_KEY_SMTRC_KODATE_START, API_KEY_SMTRC_KODATE_DETAIL,
    API_KEY_SMTRC_TOCHI_START, API_KEY_SMTRC_TOCHI_DETAIL,
    API_KEY_SMTRC_INVESTMENT_START, API_KEY_SMTRC_INVESTMENT_DETAIL,
    ParseDetailPageAsyncBase, ParseMiddlePageAsyncBase
)
from package.parser.smtrcParser import (
    SmtrcMansionParser, SmtrcKodateParser, SmtrcTochiParser, SmtrcInvestmentParser
)
from package.api.registry import ApiRegistry

DETAIL_PARARELL_LIMIT = 1

# --- Mansion ---
class ParseSmtrcMansionDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SmtrcMansionParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSmtrcMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SmtrcMansionParser()

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
        return API_KEY_SMTRC_MANSION_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SMTRC_MANSION_START


# --- Kodate ---
class ParseSmtrcKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SmtrcKodateParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSmtrcKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SmtrcKodateParser()

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
        return API_KEY_SMTRC_KODATE_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SMTRC_KODATE_START


# --- Tochi ---
class ParseSmtrcTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SmtrcTochiParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSmtrcTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SmtrcTochiParser()

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
        return API_KEY_SMTRC_TOCHI_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SMTRC_TOCHI_START


# --- Investment ---
class ParseSmtrcInvestmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return SmtrcInvestmentParser()

    def _getLocalPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getCloudPararellLimit(self):
        return DETAIL_PARARELL_LIMIT

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        return ""

class ParseSmtrcInvestmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self):
        return SmtrcInvestmentParser()

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
        return API_KEY_SMTRC_INVESTMENT_DETAIL

    def _getNextPageApiKey(self):
        return API_KEY_SMTRC_INVESTMENT_START


# Registry
ApiRegistry.register(API_KEY_SMTRC_MANSION_START, ParseSmtrcMansionStartAsync)
ApiRegistry.register(API_KEY_SMTRC_MANSION_DETAIL, ParseSmtrcMansionDetailFuncAsync)

ApiRegistry.register(API_KEY_SMTRC_KODATE_START, ParseSmtrcKodateStartAsync)
ApiRegistry.register(API_KEY_SMTRC_KODATE_DETAIL, ParseSmtrcKodateDetailFuncAsync)

ApiRegistry.register(API_KEY_SMTRC_TOCHI_START, ParseSmtrcTochiStartAsync)
ApiRegistry.register(API_KEY_SMTRC_TOCHI_DETAIL, ParseSmtrcTochiDetailFuncAsync)

ApiRegistry.register(API_KEY_SMTRC_INVESTMENT_START, ParseSmtrcInvestmentStartAsync)
ApiRegistry.register(API_KEY_SMTRC_INVESTMENT_DETAIL, ParseSmtrcInvestmentDetailFuncAsync)

