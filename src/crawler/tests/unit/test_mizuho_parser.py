# -*- coding: utf-8 -*-
"""
みずほ不動産販売 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from bs4 import BeautifulSoup
from package.utils.mizuho_bypass import get_mizuho_links
from package.parser.mizuhoParser import (
    MizuhoMansionParser,
    MizuhoKodateParser,
    MizuhoTochiParser,
    MizuhoInvestmentParser,
    MizuhoParser
)
from package.models.mizuho import (
    MizuhoMansion,
    MizuhoKodate,
    MizuhoTochi,
    MizuhoInvestment
)


def test_mizuho_mansion_parser():
    """みずほマンションパーサーのインスタンス化とエンティティ生成を検証。"""
    parser = MizuhoMansionParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoMansion)
    assert parser.property_type == 'mansion'


def test_mizuho_kodate_parser():
    """みずほ戸建てパーサーのインスタンス化とエンティティ生成を検証。"""
    parser = MizuhoKodateParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoKodate)
    assert parser.property_type == 'kodate'


def test_mizuho_tochi_parser():
    """みずほ土地パーサーのインスタンス化とエンティティ生成を検証。"""
    parser = MizuhoTochiParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoTochi)
    assert parser.property_type == 'tochi'


def test_mizuho_investment_parser():
    """みずほ投資用物件パーサーのインスタンス化とエンティティ生成を検証。"""
    parser = MizuhoInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoInvestment)
    assert parser.property_type == 'investment'


def test_mizuho_base_parse_property_detail_page_no_premature_validation(caplog):
    """
    基底クラス MizuhoParser._parsePropertyDetailPage で clean_parsed_item が
    尚早に呼ばれず、子クラスでのフィールド設定前に不要な [PARSER_EXTRACTION_ERROR]
    が出力されないことを検証。
    """
    class ConcreteMizuhoParser(MizuhoParser):
        def createEntity(self):
            return MizuhoKodate()

    parser = ConcreteMizuhoParser()
    item = MizuhoKodate()
    soup = BeautifulSoup("<html><body><div class='detailTitle'><h3 class='h3Title'>テスト物件</h3></div></body></html>", "html.parser")
    
    with caplog.at_level("ERROR"):
        res_item = parser._parsePropertyDetailPage(item, soup)
    
    # 基底パーサー呼び出し時点で [PARSER_EXTRACTION_ERROR] が出ていないこと
    extraction_errors = [r for r in caplog.records if "[PARSER_EXTRACTION_ERROR]" in r.message]
    assert len(extraction_errors) == 0
    assert res_item.propertyName == "テスト物件"


@pytest.mark.asyncio
async def test_mizuho_parse_root_page_bypass():
    """
    parseRootPage で静的HTMLにリンクがない場合、Playwrightバイパス経由で
    リンクが抽出されることを検証。
    """
    parser = MizuhoKodateParser()
    empty_soup = BeautifulSoup("<html><head><title>403</title></head><body>WAF Blocked</body></html>", "html.parser")
    
    mock_links = [
        "https://www.mizuho-re.co.jp/buyers/property/000000000001/",
        "https://www.mizuho-re.co.jp/buyers/property/000000000002/",
    ]
    with patch("package.utils.mizuho_bypass.get_mizuho_links", new_callable=AsyncMock) as mock_bypass:
        mock_bypass.return_value = mock_links
        
        extracted = []
        async for link in parser.parseRootPage(empty_soup):
            extracted.append(link)
            
        assert extracted == mock_links
        mock_bypass.assert_called_once()


@pytest.mark.asyncio
async def test_mizuho_parse_root_page_bypass_zero_links():
    """Playwrightバイパスが0件を返却した場合の挙動を検証。"""
    parser = MizuhoKodateParser()
    empty_soup = BeautifulSoup("<html><head><title>403</title></head><body>WAF Blocked</body></html>", "html.parser")
    with patch("package.utils.mizuho_bypass.get_mizuho_links", new_callable=AsyncMock) as mock_bypass:
        mock_bypass.return_value = []
        extracted = []
        async for link in parser.parseRootPage(empty_soup):
            extracted.append(link)
        assert extracted == []


@pytest.mark.asyncio
async def test_mizuho_parse_root_page_bypass_exception():
    """Playwrightバイパス処理中に例外が発生した場合の例外捕捉を検証。"""
    parser = MizuhoKodateParser()
    empty_soup = BeautifulSoup("<html><head><title>403</title></head><body>WAF Blocked</body></html>", "html.parser")
    with patch("package.utils.mizuho_bypass.get_mizuho_links", new_callable=AsyncMock) as mock_bypass:
        mock_bypass.side_effect = RuntimeError("Playwright error")
        extracted = []
        async for link in parser.parseRootPage(empty_soup):
            extracted.append(link)
        assert extracted == []


@pytest.mark.asyncio
async def test_get_mizuho_links_success():
    """Playwrightバイパス処理によるリンク抽出・正規化・クローズ処理を検証。"""
    with patch("package.utils.mizuho_bypass.async_playwright") as mock_ap:
        mock_p = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_p
        mock_ap.return_value = mock_cm

        mock_browser = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_context = AsyncMock()
        mock_context.add_init_script = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_page = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_page.set_extra_http_headers = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.mouse.move = AsyncMock()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.title = AsyncMock(return_value="みずほ不動産販売")
        mock_page.evaluate = AsyncMock(return_value=[
            "/buyers/property/000000000001/",
            "https://www.mizuho-re.co.jp/buyers/property/000000000002/",
            "javascript:void(0)"
        ])

        links = await get_mizuho_links("https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/")
        assert links == [
            "https://www.mizuho-re.co.jp/buyers/property/000000000001/",
            "https://www.mizuho-re.co.jp/buyers/property/000000000002/"
        ]
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_mizuho_links_403_and_close_exceptions():
    """Playwrightバイパスで403検出時およびクローズ時例外のハンドリングを検証。"""
    with patch("package.utils.mizuho_bypass.async_playwright") as mock_ap:
        mock_p = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_p
        mock_ap.return_value = mock_cm

        mock_browser = AsyncMock()
        mock_browser.close = AsyncMock(side_effect=RuntimeError("Browser close fail"))
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_context = AsyncMock()
        mock_context.close = AsyncMock(side_effect=RuntimeError("Context close fail"))
        mock_context.add_init_script = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_page = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_page.set_extra_http_headers = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.mouse.move = AsyncMock()

        mock_response = MagicMock()
        mock_response.status = 403
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.title = AsyncMock(return_value="403 Forbidden")

        links = await get_mizuho_links("https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/")
        assert links == []


@pytest.mark.asyncio
async def test_get_mizuho_links_launch_exception():
    """Playwright初期化時の例外捕捉を検証。"""
    with patch("package.utils.mizuho_bypass.async_playwright") as mock_ap:
        mock_ap.side_effect = RuntimeError("Launch failed")
        links = await get_mizuho_links("https://www.mizuho-re.co.jp/test")
        assert links == []

