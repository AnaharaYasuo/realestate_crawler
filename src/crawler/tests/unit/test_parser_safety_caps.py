import os
from unittest.mock import patch
from package.parser.baseParser import ParserBase


class DummyParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyName(self, response, specs=None):
        return ""

    def _parsePriceStr(self, response, specs=None):
        return ""

    def _parsePrice(self, response, specs=None):
        return None

    def _parseAddress(self, response, specs=None):
        return ""

    def _parseTransport1(self, response, specs=None):
        return ""

    def _parsePropertyDetailPage(self, item, response):
        return item


def test_parser_safety_caps_defaults():
    """Verify default safety caps prevent accidental early termination."""
    with patch.dict(os.environ, {}, clear=True):
        parser = DummyParser()
        assert parser.MAX_PAGES_PER_JOB == 2000
        assert parser.MAX_PROPERTIES_PER_JOB == 50000


def test_parser_safety_caps_env_override():
    """Verify safety caps can be dynamically overridden via valid positive integers."""
    with patch.dict(
        os.environ,
        {"MAX_PAGES_PER_JOB": "500", "MAX_PROPERTIES_PER_JOB": "12000"},
        clear=True,
    ):
        parser = DummyParser()
        assert parser.MAX_PAGES_PER_JOB == 500
        assert parser.MAX_PROPERTIES_PER_JOB == 12000


def test_parser_safety_caps_invalid_env_fallback():
    """Verify safety caps fall back to safe defaults when env values are invalid."""
    with patch.dict(
        os.environ,
        {"MAX_PAGES_PER_JOB": "invalid", "MAX_PROPERTIES_PER_JOB": "-10"},
        clear=True,
    ):
        parser = DummyParser()
        assert parser.MAX_PAGES_PER_JOB == 2000
        assert parser.MAX_PROPERTIES_PER_JOB == 50000
