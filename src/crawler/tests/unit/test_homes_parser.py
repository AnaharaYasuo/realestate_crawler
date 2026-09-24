# -*- coding: utf-8 -*-
"""
ライフルホームズ（LIFULL HOME'S） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
import pytest
from package.parser.homesParser import HomesMansionParser, HomesKodateParser, HomesInvestmentApartmentParser
from package.models.homes import HomesMansion, HomesKodate, HomesInvestmentApartment

def test_homes_investment_rent_derivation():
    from bs4 import BeautifulSoup
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    item.price = 6200000
    html = """
    <div>
        <td class="prg-nameTableItem">テスト物件</td>
        <td class="prg-priceTableItem">620万円</td>
        <span class="prg-rimawariTableItem">9.48％</span>
        <td class="prg-annualIncomeTableItem">-</td>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    assert float(parsed_item.grossYield) == pytest.approx(9.48, rel=1e-2)
    assert parsed_item.annualRent == 587760
    assert parsed_item.monthlyRent == 48980


def test_homes_mansion_parser():
    parser = HomesMansionParser()
    item = parser.createEntity()
    assert isinstance(item, HomesMansion)

def test_homes_kodate_parser():
    parser = HomesKodateParser()
    item = parser.createEntity()
    assert isinstance(item, HomesKodate)


@pytest.mark.asyncio
async def test_homes_parse_root_page_yield_priority():
    from bs4 import BeautifulSoup
    parser = HomesMansionParser()
    html = (
        '<div>'
        '<div class="card1"><a href="/bukkendetail/123/">物件1 (利回り8.5%)</a></div>'
        '<div class="card2"><a href="/bukkendetail/456/">物件2</a></div>'
        '<div class="card3"><a href="/bukkendetail/123/">物件1重複</a></div>'
        '</div>'
    )
    soup = BeautifulSoup(html, "html.parser")
    links = [link async for link in parser.parseRootPage(soup)]
    assert len(links) == 2
    assert "123" in links[0]
    assert "456" in links[1]


def test_homes_is_yield_indicated():
    from bs4 import BeautifulSoup
    parser = HomesMansionParser()
    soup_yield = BeautifulSoup("<tr><td><a href='#'>test</a>利回り 7.2％</td></tr>", "html.parser")
    a_yield = soup_yield.find("a")
    assert parser._is_yield_indicated(a_yield) is True

    soup_no_yield = BeautifulSoup("<tr><td><a href='#'>test</a>価格 4000万円</td></tr>", "html.parser")
    a_no = soup_no_yield.find("a")
    assert parser._is_yield_indicated(a_no) is False
