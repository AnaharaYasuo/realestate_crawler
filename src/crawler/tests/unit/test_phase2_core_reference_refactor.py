"""Unit tests for Phase 2 core reference refactoring (Models, Parsers, API)."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from package.api.api import ApiAsyncProcBase, header
from package.models.base import (
    InvestmentBaseModel,
    KodateBaseModel,
    MansionBaseModel,
    PropertyBaseModel,
    TochiBaseModel,
    TransportationMixin,
)
from package.parser.investmentParser import InvestmentParser


def test_investment_base_model_exists_and_inherits_property_base():
    assert issubclass(InvestmentBaseModel, PropertyBaseModel)
    assert issubclass(InvestmentBaseModel, TransportationMixin)
    assert InvestmentBaseModel._meta.abstract is True
    field_names = {f.name for f in InvestmentBaseModel._meta.get_fields()}
    for expected in (
        "grossYield",
        "annualRent",
        "monthlyRent",
        "currentStatus",
        "tochiMenseki",
        "tatemonoMenseki",
        "chikunengetsu",
        "kouzou",
        "kaisu",
        "youtoChiiki",
        "kenpei",
        "youseki",
    ):
        assert expected in field_names, f"Missing {expected} on InvestmentBaseModel"


def test_investment_parser_parse_price_decimal_oku_no_10x_bug():
    class DummyInvestmentParser(InvestmentParser):
        def createEntity(self):
            return None

    parser = DummyInvestmentParser()
    assert parser._parse_price("1.5億円") == 150_000_000
    assert parser._parse_price("2.35億円") == 235_000_000
    assert parser._parse_price("1億5,000万円") == 150_000_000
    assert parser._parse_price("5,980万円") == 59_800_000
    assert parser._parse_price("120,000,000円") == 120_000_000
    assert parser._parse_price("120000000") == 120_000_000
    assert parser._parse_price("") is None
    assert parser._parse_price("相談") is None


def test_sumifu_parser_no_importlib_reload_sys():
    sumifu_path = Path(__file__).resolve().parents[2] / "package" / "parser" / "sumifuParser.py"
    source = sumifu_path.read_text(encoding="utf-8")
    assert "reload(sys)" not in source


@pytest.mark.asyncio
async def test_api_user_agent_modernized_and_shared_session_reuse():
    assert "Windows NT 6.1" not in ApiAsyncProcBase.USER_AGENT
    assert ApiAsyncProcBase.USER_AGENT == header["User-Agent"]

    class DummyApi(ApiAsyncProcBase):
        def _generateParser(self):
            return MagicMock()

        def _getPararellLimit(self):
            return 2

        def _getLocalPararellLimit(self):
            return 2

        def _getCloudPararellLimit(self):
            return 2

        def _getTimeOutSecond(self):
            return 30

        def _getApiKey(self):
            return "/test"

        def _getTreatPageArg(self):
            return None

        async def _treatPage(self, _session, *arg):
            return []

        async def _callApi(self, url_list):
            return []

    api = DummyApi()
    mock_session = MagicMock()
    mock_session.closed = False
    api._shared_session = mock_session
    api._fetch = AsyncMock(return_value=("https://example.com/1", 200, "OK"))

    res = await api._fetchWithEachSession("https://example.com/1", "http://127.0.0.1:8000/test", None)
    assert res == ("https://example.com/1", 200, "OK")
    api._fetch.assert_awaited_once_with(
        mock_session, "https://example.com/1", "http://127.0.0.1:8000/test", None, retry_times=0
    )
