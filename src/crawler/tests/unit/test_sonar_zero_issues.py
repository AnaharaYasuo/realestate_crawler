import inspect
import re
import pytest
from bs4 import BeautifulSoup
from package.utils.crawl_smoke_engine import _discover_repros_json_details
from package.parser.heimParser import HeimMansionParser
from package.parser.mitsuiParser import MitsuiMansionParser
from package.parser.nomuraParser import NomuraMansionParser
from package.parser.sumifuParser import SumifuMansionParser
from package.parser.tokyuParser import TokyuMansionParser
from package.parser.baseParser import ParserBase
from package.utils.deduplication import normalize_address
import package.api.mitsui as mitsui_api
import package.api.sumifu as sumifu_api
import package.api.tokyu as tokyu_api


def test_no_identical_return_branches_in_api_key():
    """Verify that _getApiKey does not have redundant identical return branches (python:S3516)."""
    for mod in [mitsui_api, sumifu_api, tokyu_api]:
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if hasattr(cls, '_getApiKey'):
                src = inspect.getsource(cls._getApiKey)
                # Ensure no 'if os.getenv ... return "" return ""' pattern exists
                assert "if os.getenv" not in src or "return \"\"" not in src, f"{cls.__name__} has redundant _getApiKey branches"


def test_repros_json_details_return_type():
    """Verify _discover_repros_json_details returns None (python:S3516)."""
    sig = inspect.signature(_discover_repros_json_details)
    assert sig.return_annotation in (None, type(None), "None")


def test_soukosu_naming_conflict_resolved():
    """Verify _parseSouKosu is present and _parseSoukosu does not conflict (python:S1845)."""
    for cls in [HeimMansionParser, MitsuiMansionParser, NomuraMansionParser, SumifuMansionParser, TokyuMansionParser]:
        assert hasattr(cls, "_parseSouKosu"), f"{cls.__name__} must implement _parseSouKosu"
        # Method dict must not define both _parseSouKosu and _parseSoukosu as separate functions
        raw_dict = cls.__dict__
        if "_parseSoukosu" in raw_dict and "_parseSouKosu" in raw_dict:
            # If both exist, _parseSoukosu must be an alias to _parseSouKosu or delegated
            assert raw_dict["_parseSoukosu"] == raw_dict["_parseSouKosu"] or inspect.getsource(raw_dict["_parseSoukosu"]).strip().endswith("self._parseSouKosu(response, specs)")


def test_unreachable_yield_eliminated_in_base_parser():
    """Verify baseParser.parsePropertyListPage does not contain unreachable yield (python:S1763)."""
    src = inspect.getsource(ParserBase.parsePropertyListPage)
    assert "yield" not in src or "return\n        yield" not in src


def test_show_migrations_no_trailing_junk():
    """Verify show_migrations.py has no trailing non-ascii characters (python:S905)."""
    with open("src/crawler/scripts/debug_tools/show_migrations.py", "rb") as f:
        content = f.read().decode("utf-8")
    assert "ー" not in content


def test_clean_address_deduplication():
    """Verify clean_address removes duplicates in character classes and handles full-width spaces (python:S5869, S6035)."""
    addr = "東京都　新宿区　西新宿１丁目２番地３号"
    cleaned = normalize_address(addr)
    assert cleaned == "東京都新宿区西新宿1-2-3"

