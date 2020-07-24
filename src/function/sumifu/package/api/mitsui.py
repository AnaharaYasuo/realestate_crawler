import os

from package.api.api import API_KEY_MITSUI_DETAIL_GCP, API_KEY_MITSUI_DETAIL, API_KEY_MITSUI_AREA_GCP, API_KEY_MITSUI_AREA, API_KEY_MITSUI_LIST_GCP, API_KEY_MITSUI_LIST, ParseDetailPageAsyncBase,ParseMiddlePageAsyncBase
from package.parser.mitsuiParser import MitsuiMansionParser


class ParseMitsuiDetailFuncAsync(ParseDetailPageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")

    def _getLocalPararellLimit(self):
        return 3

    def _getCloudPararellLimit(self):
        return 3

    def _getTimeOutSecond(self):
        return 60

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return ""
        return ""
    
class ParseMitsuiListFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parsePropertyListPage

    def _getLocalPararellLimit(self):
        return 3

    def _getCloudPararellLimit(self):
        return 3

    def _getTimeOutSecond(self):
        return 300

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_DETAIL_GCP
        return API_KEY_MITSUI_DETAIL
    

class ParseMitsuiAreaFuncAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseAreaPage

    def _getLocalPararellLimit(self):
        return 5

    def _getCloudPararellLimit(self):
        return 5

    def _getTimeOutSecond(self):
        return 1800

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_LIST_GCP
        return API_KEY_MITSUI_LIST
    
class ParseMitsuiStartAsync(ParseMiddlePageAsyncBase):

    def _generateParser(self):
        return MitsuiMansionParser("")
    
    def _getParserFunc(self):
        return self.parser.parseRootPage

    def _getLocalPararellLimit(self):
        return 8

    def _getCloudPararellLimit(self):
        return 8

    def _getTimeOutSecond(self):
        return 1800

    def _getApiKey(self):
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_MITSUI_AREA_GCP
        return API_KEY_MITSUI_AREA