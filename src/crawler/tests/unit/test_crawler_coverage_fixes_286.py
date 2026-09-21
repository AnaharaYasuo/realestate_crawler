# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup


def test_daiwa_tailwind_pagination():
    """大和ハウスのTailwind CSSページネーションから次ページURLが正常に抽出されること"""
    from package.parser.daiwaParser import DaiwaMansionParser

    html = """
    <div>
        <div class="search-result-items">
            <a href="/buy/mansion/prop1">物件1</a>
        </div>
        <div class="pagination-container">
            <a class="flex h-[3rem] w-[3rem] items-center justify-center" href="/buy/search/alist?property_type%5B%5D=2&page=2">2</a>
            <a class="flex h-[3rem] w-[3rem] items-center justify-center" href="/buy/search/alist?property_type%5B%5D=2&page=3">3</a>
            <a class="bg-gray_939393 flex h-[3rem] w-[3rem] items-center justify-center" href="/buy/search/alist?property_type%5B%5D=2&page=2">
                <svg><path></path></svg>
            </a>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = DaiwaMansionParser()

    import asyncio
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert next_url is not None
    assert "page=2" in next_url
    assert next_url.startswith("https://www.dh-realestate.co.jp")


def test_daikyo_pagination():
    """大京の .jsPagingNext / .result-pager__link から次ページURLが正常に抽出されること"""
    from package.parser.daikyoParser import DaikyoMansionParser

    html = """
    <div>
        <div class="result-pager">
            <a class="result-pager__link" href="https://www.daikyo-anabuki.co.jp/buy/mansion/p13/?page=2">2</a>
            <a class="jsPagingNext" href="https://www.daikyo-anabuki.co.jp/buy/mansion/p13/?page=2">次へ</a>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = DaikyoMansionParser()

    import asyncio
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert next_url is not None
    assert "page=2" in next_url


def test_keio_referer_header():
    """京王不動産のAPI取得でRefererヘッダが付与されていること"""
    from package.parser.keioParser import KeioMansionParser

    parser = KeioMansionParser()
    headers = parser._get_request_headers()
    assert "Referer" in headers
    assert "keiofudosan.co.jp" in headers["Referer"]


def test_mitsui_area_city_drilldown():
    """三井のエリア選択から各市区町村URLが抽出できること"""
    import lxml.html
    from package.parser.mitsuiParser import MitsuiMansionParser

    html = """
    <div>
        <a class="link" href="/buy/mansion/prefecture/13/city/13101/">千代田区</a>
        <a class="link" href="/buy/mansion/prefecture/13/city/13102/">中央区</a>
        <a class="link" href="/buy/mansion/prefecture/13/city/13103/">港区</a>
    </div>
    """
    tree = lxml.html.fromstring(html)
    parser = MitsuiMansionParser()
    xpath = parser.getAreaXpath()
    links = tree.xpath(xpath)
    assert len(links) >= 3
    assert any("13101" in link for link in links)


def test_odakyu_nationwide_and_parser():
    """小田急の全エリアルートおよびパーサー（居住用・投資用）が正しく機能すること"""
    import asyncio
    from package.parser.odakyuParser import OdakyuKodateParser
    from routes.odakyu_routes import get_start_url

    assert get_start_url("mansion") == "https://www.odakyu-chukai.com/mansion/list/"
    assert get_start_url("kodate") == "https://www.odakyu-chukai.com/house/list/"
    assert get_start_url("tochi") == "https://www.odakyu-chukai.com/land/list/"

    html = """
    <div class="estate">
        <a href="/house/detail/B01425-001151/">一戸建て物件1</a>
        <div class="pagenation-block">
            <a href="https://www.odakyu-chukai.com/house/list/?per=30&page=2">次へ</a>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = OdakyuKodateParser()

    async def _collect():
        return [u async for u in parser.parseRootPage(soup)]

    items = asyncio.run(_collect())
    assert len(items) == 1
    assert "B01425-001151" in items[0]

    next_page = asyncio.run(parser.parseNextPage(soup))
    assert "page=2" in next_page


def test_homes_nationwide_routes():
    """HomesのスタートURLが東京限定から全国検索クエリへ拡張されていること"""
    import asyncio
    from package.parser.homesParser import HomesInvestmentApartmentParser

    html = """
    <div>
        <link href="https://toushi.homes.co.jp/bukkensearch/tbg[]=1/" rel="canonical"/>
        <a href="/bukkendetail/index/1234567/">詳細</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = HomesInvestmentApartmentParser()
    next_page = asyncio.run(parser.parseNextPage(soup))
    assert next_page == "https://toushi.homes.co.jp/bukkensearch/tbg[]=1/?page=2"
