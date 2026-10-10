"""Unit tests for hierarchy parallelization and list-price skip optimization (#854).

Verifies that all 15 target parsers extract ListItem(url, price) correctly from list/card HTML.
Target parsers:
- smtrc, sumirin, odakyu, keikyu, keisei, seibu, sotetsu, sumai1, rearie
- adcast, haseko, ietan, toho, kenbiya, mitsui
"""

import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock
from package.parser.adcastParser import AdCastKodateParser
from package.parser.baseParser import ListItem
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.ietanParser import IetanMansionParser
from package.parser.keikyuParser import KeikyuMansionParser
from package.parser.keiseiParser import KeiseiMansionParser
from package.parser.kenbiyaParser import KenbiyaMansionParser
from package.parser.mitsuiParser import MitsuiMansionParser
from package.parser.odakyuParser import OdakyuMansionParser
from package.parser.rearieParser import RearieMansionParser
from package.parser.seibuParser import SeibuMansionParser
from package.parser.smtrcParser import SmtrcMansionParser
from package.parser.sotetsuParser import SotetsuMansionParser
from package.parser.sumai1Parser import Sumai1MansionParser
from package.parser.sumirinParser import SumirinMansionParser
from package.parser.tohoParser import TohoMansionParser


@pytest.mark.asyncio
async def test_smtrc_parse_root_page_yields_list_item():
    parser = SmtrcMansionParser()
    html = """
    <div class="cassette">
        <span class="price">4,580万円</span>
        <a href="/detail/CompareDetails?propertyCode=12345">物件詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert "propertyCode=12345" in items[0].url
    assert items[0].price == 45800000


@pytest.mark.asyncio
async def test_sumirin_parse_root_page_yields_list_item():
    parser = SumirinMansionParser()
    html = """
    <div class="property-item">
        <div class="property-price">5,280万円</div>
        <a href="/buy/estate/estateInfo/mansion/tokyo/98765/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 52800000


@pytest.mark.asyncio
async def test_odakyu_parse_root_page_yields_list_item():
    parser = OdakyuMansionParser()
    html = """
    <div class="bukken_box">
        <span class="num">3,980</span>万円
        <a href="/mansion/detail/111/">詳細を見る</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 39800000


@pytest.mark.asyncio
async def test_keikyu_parse_root_page_yields_list_item():
    parser = KeikyuMansionParser()
    html = """
    <div class="item-card">
        <p class="price-val">6,100万円</p>
        <a href="/detail/keikyu_222/">物件を見る</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 61000000


@pytest.mark.asyncio
async def test_keisei_parse_root_page_yields_list_item():
    parser = KeiseiMansionParser()
    html = """
    <div class="card">
        <span class="price">2,480万円</span>
        <a href="/detail/keisei_333.html">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 24800000


@pytest.mark.asyncio
async def test_seibu_parse_root_page_yields_list_item():
    parser = SeibuMansionParser()
    html = """
    <div class="box">
        <span class="price-txt">7,300万円</span>
        <a href="/detail/seibu_444/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 73000000


@pytest.mark.asyncio
async def test_sotetsu_parse_root_page_yields_list_item():
    parser = SotetsuMansionParser()
    html = """
    <div class="cassette">
        <span class="price">4,180万円</span>
        <a href="/buy/view/sotetsu_555.html">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 41800000


@pytest.mark.asyncio
async def test_sumai1_parse_root_page_yields_list_item():
    parser = Sumai1MansionParser()
    html = """
    <div class="property-block">
        <div class="price">8,800万円</div>
        <a href="/buyers/mansion/bukken/buk_666/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 88000000


@pytest.mark.asyncio
async def test_rearie_parse_root_page_yields_list_item():
    parser = RearieMansionParser()
    html = """
    <div class="bukken">
        <span class="price">3,200万円</span>
        <a href="detail.html?id=777&mansion=1">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 32000000


@pytest.mark.asyncio
async def test_rearie_parse_root_page_json_yields_list_item():
    parser = RearieMansionParser()
    mock_resp = MagicMock()
    mock_resp._json_data = {"list": [{"id": "json_1", "price": 4200}]}
    items = [item async for item in parser.parseRootPage(mock_resp)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert "id=json_1" in items[0].url
    assert items[0].price == 42000000


@pytest.mark.asyncio
async def test_adcast_parse_property_list_page_yields_list_item():
    parser = AdCastKodateParser()
    html = """
    <div class="cassette">
        <span class="price">6,480万円</span>
        <a href="/detail/adcast_888/">物件詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 64800000


@pytest.mark.asyncio
async def test_haseko_parse_property_list_page_yields_list_item():
    parser = HasekoMansionParser()
    html = """
    <div class="card">
        <span class="price">5,980万円</span>
        <a href="/detail/haseko_999.html">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 59800000


@pytest.mark.asyncio
async def test_ietan_parse_property_list_page_yields_list_item():
    parser = IetanMansionParser()
    html = """
    <div class="item">
        <span class="price">3,500万円</span>
        <a href="/detail/ietan_101.html">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 35000000


@pytest.mark.asyncio
async def test_toho_parse_property_list_page_yields_list_item():
    parser = TohoMansionParser()
    html = """
    <div class="cassette">
        <span class="price">4,890万円</span>
        <a href="/detail/toho_202.html">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 48900000


@pytest.mark.asyncio
async def test_kenbiya_parse_property_list_page_yields_list_item():
    parser = KenbiyaMansionParser()
    html = """
    <div class="card">
        <span class="price">1億2,000万円</span>
        <a href="/pp1/detail/re_303/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 120000000


@pytest.mark.asyncio
async def test_mitsui_parse_property_list_page_yields_list_item():
    parser = MitsuiMansionParser()
    html = """
    <div class="property-index-card">
        <span class="text-price-regular">7,980万円</span>
        <a href="/buy/mansion/bkdetail/mitsui_404/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert isinstance(items[0], ListItem)
    assert items[0].price == 79800000
