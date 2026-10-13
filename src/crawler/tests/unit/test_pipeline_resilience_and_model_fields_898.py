import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from package.models.mitsui import MitsuiInvestmentApartment, MitsuiMansion
from package.models.sumifu import SumifuKodate
from package.parser.baseParser import (
    LoadPropertyPageException,
    ParserBase,
    ServerDownException,
)

def test_sumifu_kodate_empty_optional_fields_pass_validation():
    """SumifuKodate accepts blank strings for regional/zoning fields without ValidationError."""
    item = SumifuKodate(
        pageUrl="https://www.stepon.co.jp/kodate/detail_test/",
        propertyName="テスト戸建",
        priceStr="3000万円",
        price=30000000,
        address="東京都墨田区",
        hikiwatashi="相談",
        genkyo="空家",
        tochikenri="所有権",
        torihiki="仲介",
        tochiMensekiStr="100m2",
        tochiMenseki=100.0,
        tatemonoMensekiStr="90m2",
        tatemonoMenseki=90.0,
        madori="3LDK",
        chikunengetsuStr="2000年1月",
        kaisuKouzou="2階建木造",
        chimokuChisei="宅地平坦",
        chimoku="宅地",
        chisei="平坦",
        kenpeiYousekiStr="60%/200%",
        chiikiChiku="",
        kuiki="",
        youtoChiiki="",
        boukaChiiki="",
        saikenchiku="",
        sonotaChiiki="",
        kokudoHou="",
    )
    # This should not raise ValidationError for chiikiChiku, boukaChiiki, saikenchiku, sonotaChiiki
    item.full_clean()
    assert item.chiikiChiku == ""
    assert item.boukaChiiki == ""

def test_mitsui_mansion_none_kanrihi_syuzen_pass_validation():
    """MitsuiMansion accepts None/blank for kanrihi and syuzenTsumitate."""
    item = MitsuiMansion(
        pageUrl="https://www.rehouse.co.jp/buy/mansion/bkdetail/FL2BSA16/",
        propertyName="テストマンション",
        priceStr="5000万円",
        price=50000000,
        address="神奈川県横浜市",
        kanrihi=None,
        kanrihiStr="",
        syuzenTsumitate=None,
        syuzenTsumitateStr="",
    )
    item.full_clean()
    assert item.kanrihi is None
    assert item.syuzenTsumitate is None

def test_mitsui_investment_apartment_empty_soukosu_str_pass_validation():
    """MitsuiInvestmentApartment accepts blank soukosuStr and None soukosu."""
    item = MitsuiInvestmentApartment(
        pageUrl="https://www.rehouse.co.jp/buy/kodate/bkdetail/F7HBGA12/",
        propertyName="メゾンドヴェルディ",
        priceStr="10000万円",
        price=100000000,
        address="東京都渋谷区",
        grossYield=5.5,
        annualRent=5500000,
        monthlyRent=458333,
        currentStatus="賃貸中",
        kouzou="RC造",
        chikunengetsuStr="1995年4月",
        soukosuStr="",
        soukosu=None,
        propertyType="Apartment",
    )
    item.full_clean()
    assert item.soukosuStr == ""
    assert item.soukosu is None

@pytest.mark.asyncio
async def test_base_parser_single_url_retries_do_not_trigger_immediate_circuit_breaker():
    """Single URL timing out multiple times in internal retry loop should raise LoadPropertyPageException, not ServerDownException."""
    class DummyParser(ParserBase):
        property_type = 'mansion'
        def createEntity(self):
            return None
        def parsePropertyDetailPage(self, session, url):
            return None
        def _parsePropertyDetailPage(self, item, response):
            return item
        def _parsePropertyName(self, response):
            return "name"
        def _parsePrice(self, response):
            return 1000
        def _parsePriceStr(self, response):
            return "1000万円"
        def _parseAddress(self, response):
            return "address"
        def _parseTransport1(self, response):
            return "traffic"
        def getCharset(self):
            return "utf-8"

    parser = DummyParser()
    parser.consecutive_timeouts = 0
    parser.MAX_CONSECUTIVE_TIMEOUTS = 3

    mock_session = MagicMock()
    mock_session.get.side_effect = asyncio.TimeoutError()

    with patch('asyncio.sleep', new_callable=AsyncMock):
        # 1st URL fails all 3 internal attempts -> raises LoadPropertyPageException, consecutive_timeouts becomes 1
        with pytest.raises(LoadPropertyPageException):
            await parser._getContent(mock_session, "https://example.com/p1")
        assert parser.consecutive_timeouts == 1

        # 2nd URL fails all 3 internal attempts -> raises LoadPropertyPageException, consecutive_timeouts becomes 2
        with pytest.raises(LoadPropertyPageException):
            await parser._getContent(mock_session, "https://example.com/p2")
        assert parser.consecutive_timeouts == 2

        # 3rd URL fails all 3 internal attempts -> consecutive_timeouts reaches 3, raises ServerDownException
        with pytest.raises(ServerDownException):
            await parser._getContent(mock_session, "https://example.com/p3")
        assert parser.consecutive_timeouts >= 3
