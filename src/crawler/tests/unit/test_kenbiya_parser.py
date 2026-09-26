# -*- coding: utf-8 -*-
from decimal import Decimal
import inspect
import pytest

from package.parser.baseParser import InvestmentParserBase, RateLimitedException
from package.utils.url_router import UrlRouter


def test_kenbiya_parser_inherits_investment_base():
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser

    assert issubclass(KenbiyaInvestmentApartmentParser, InvestmentParserBase)
    # Ensure all abstract methods are implemented
    assert not inspect.isabstract(KenbiyaInvestmentApartmentParser)


def test_url_router_kenbiya_resolution():
    routes = [
        ("https://www.kenbiya.com/pp1/s/tokyo/adachi-ku/re_47223989xb/", "kenbiya", "mansion", "KenbiyaMansionParser", "KenbiyaMansion"),
        ("https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/", "kenbiya", "apartment", "KenbiyaInvestmentApartmentParser", "KenbiyaInvestmentApartment"),
        ("https://www.kenbiya.com/pp3/s/tokyo/adachi-ku/re_4721852cvo/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp4/s/tokyo/adachi-ku/re_4720631znv/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp8/s/tokyo/adachi-ku/re_4720946geb/", "kenbiya", "kodate", "KenbiyaKodateParser", "KenbiyaKodate"),
        ("https://www.kenbiya.com/pp5/s/tokyo/adachi-ku/re_4718878jfv/", "kenbiya", "tochi", "KenbiyaTochiParser", "KenbiyaTochi"),
    ]
    for url, site, ptype, parser_name, model_name in routes:
        route = UrlRouter.resolve(url)
        assert route is not None, f"Failed to route {url}"
        assert route["site"] == site
        assert route["property_type"] == ptype
        assert route["parser_cls"] == parser_name
        assert route["model_cls"] == model_name


def test_kenbiya_parser_edge_cases():
    from package.parser.kenbiyaParser import KenbiyaMansionParser, KenbiyaTochiParser

    m_parser = KenbiyaMansionParser()
    # Test _parseMadori variations
    assert m_parser._parseMadori(None, {"間取り": ""}) == ""
    assert m_parser._parseMadori(None, {"間取り": "ワンルーム 南向き"}) == "ワンルーム"
    assert m_parser._parseMadori(None, {"間取り": "3LDK 南向き"}) == "3LDK"
    assert m_parser._parseMadori(None, {"間取り": "その他詳細 2DK"}) == "2DK"
    assert m_parser._parseMadori(None, {"間取り": "不明フォーマット"}) == "不明フォーマット"

    # Test _parseFloor and _parseTotalFloor variations
    assert m_parser._parseFloor(None, {"階数": "所在階 4階"}) == 4
    assert m_parser._parseFloor(None, {}) is None
    assert m_parser._parseTotalFloor(None, {"総階数": "地上10階"}) == 10
    assert m_parser._parseTotalFloor(None, {}) is None

    # Test _parseSenyuMenseki and _parseBalconyMenseki variations
    assert m_parser._parseSenyuMenseki(None, {"専有面積": ""}) is None
    assert m_parser._parseSenyuMenseki(None, {"専有面積": "55.4㎡"}) == Decimal("55.4")
    assert m_parser._parseBalconyMenseki(None, {"専有面積": "55.4㎡"}) is None

    # Test _parseMaguchi variations
    t_parser = KenbiyaTochiParser()
    assert t_parser._parseMaguchi(None, {"接道状況": "間口 8.5m 公道"}) == Decimal("8.5")
    assert t_parser._parseMaguchi(None, {}) is None


@pytest.mark.asyncio
async def test_kenbiya_get_content_429_rate_limited():
    """HTTP 429が連続した場合、RateLimitedException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import RateLimitedException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 2

    mock_resp = MagicMock()
    mock_resp.status = 429

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock()

    with pytest.raises(RateLimitedException) as excinfo:
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")

    assert "rate limited (429)" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation():
    """リトライ毎に異なる最新ブラウザの User-Agent が適用されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 3

    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 429
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock()
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    try:
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")
    except RateLimitedException:
        pass

    assert len(recorded_uas) == 3
    assert len(set(recorded_uas)) > 1
    assert any("Chrome/13" in ua for ua in recorded_uas)


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation_across_calls():
    """複数回の独立した _getContent 呼び出しにおいても User-Agent が切り替わること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"<html></html>")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock()
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    for _ in range(3):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")

    assert len(recorded_uas) == 3
    # 呼び出しを跨いでも3回すべて異なるUAが選択されること
    assert len(set(recorded_uas)) == 3


@pytest.mark.asyncio
async def test_kenbiya_get_content_404_listing_ended():
    """404 / 410 応答時に ListingEndedException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ListingEndedException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 404
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(ListingEndedException):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test_404")


@pytest.mark.asyncio
async def test_kenbiya_get_content_500_server_busy():
    """500 / 503 応答時に ServerBusyException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ServerBusyException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 503
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(ServerBusyException):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test_503")


@pytest.mark.asyncio
async def test_kenbiya_get_content_generic_error():
    """403 などの非対応エラーコード時に LoadPropertyPageException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import LoadPropertyPageException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(LoadPropertyPageException):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test_403")


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation_across_subclasses():
    """異なる具象パーサーサブクラス間でも共有カウンターで User-Agent がローテーションすること"""
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser, KenbiyaMansionParser
    from unittest.mock import AsyncMock, MagicMock

    parser1 = KenbiyaInvestmentApartmentParser()
    parser2 = KenbiyaMansionParser()

    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"<html></html>")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    # 1つ目のパーサーで実行
    await parser1._getContent(mock_session, "https://www.kenbiya.com/test_p1")
    # 2つ目の異なるパーサーで実行
    await parser2._getContent(mock_session, "https://www.kenbiya.com/test_p2")

    assert len(recorded_uas) == 2
    # サブクラスが異なっても直前のUAを引き継がず次の異なるUAが選択されること
    assert recorded_uas[0] != recorded_uas[1]






