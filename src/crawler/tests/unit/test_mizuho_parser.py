# -*- coding: utf-8 -*-
"""
みずほ不動産販売 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
import pytest
from unittest.mock import patch, AsyncMock
from bs4 import BeautifulSoup
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
    parser = MizuhoMansionParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoMansion)
    assert parser.property_type == 'mansion'


def test_mizuho_kodate_parser():
    parser = MizuhoKodateParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoKodate)
    assert parser.property_type == 'kodate'


def test_mizuho_tochi_parser():
    parser = MizuhoTochiParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoTochi)
    assert parser.property_type == 'tochi'


def test_mizuho_investment_parser():
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
