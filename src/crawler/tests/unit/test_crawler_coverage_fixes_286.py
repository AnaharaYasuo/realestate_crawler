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
    assert next_url.startswith("https://www.dh-realestate.co.jp/")


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
    assert headers["Referer"] == "https://chukai.keiofudosan.co.jp/"


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


def test_daikyo_parser_all_branches():
    """大京パーサーの各ブランチ（ページネーション、詳細URL正規化、都道府県展開）の網羅検証"""
    import asyncio
    from unittest.mock import AsyncMock
    from package.parser.daikyoParser import DaikyoMansionParser, DaikyoKodateParser, DaikyoTochiParser

    parser = DaikyoMansionParser()

    # 1. 汎用 .pager a による次ページ
    html_pager = '<div class="pager"><a href="/buy/mansion/p13/?page=3">次へ</a></div>'
    soup_pager = BeautifulSoup(html_pager, "html.parser")
    assert "page=3" in asyncio.run(parser.parseNextPage(soup_pager))

    # 2. page=N パラメータを持つリンク
    html_param = '<div><a href="/buy/mansion/p13/?page=4" class="jsPagingNext">4</a></div>'
    soup_param = BeautifulSoup(html_param, "html.parser")
    assert "page=4" in asyncio.run(parser.parseNextPage(soup_param))

    # 3. 該当なしで空文字返却
    html_none = '<div><span>1</span></div>'
    assert asyncio.run(parser.parseNextPage(BeautifulSoup(html_none, "html.parser"))) == ""

    # 4. _normalize_detail_url
    assert parser._normalize_detail_url("/buy/mansion/detail/123") == "https://www.daikyo-anabuki.co.jp/buy/mansion/detail/123/"
    assert parser._normalize_detail_url("https://www.daikyo-anabuki.co.jp/buy/mansion/detail/456/") == "https://www.daikyo-anabuki.co.jp/buy/mansion/detail/456/"

    # 5. _extract_pref_urls (mansion, kodate, tochi)
    html_top = """
    <div>
        <a href="/buy/mansion/p13/">東京都</a>
        <a href="/buy/mansion/p14/">神奈川県</a>
        <a href="/buy/house/p13/">東京戸建</a>
        <a href="/buy/land/p13/">東京土地</a>
    </div>
    """
    soup_top = BeautifulSoup(html_top, "html.parser")
    m_prefs = parser._extract_pref_urls(soup_top)
    assert any("p13" in u for u in m_prefs)

    kodate_parser = DaikyoKodateParser()
    k_prefs = kodate_parser._extract_pref_urls(soup_top)
    assert any("house/p13" in u for u in k_prefs)

    tochi_parser = DaikyoTochiParser()
    t_prefs = tochi_parser._extract_pref_urls(soup_top)
    assert any("land/p13" in u for u in t_prefs)

    # 6. parseRootPage 直接詳細URLがある場合
    async def _collect(gen):
        return [x async for x in gen]

    html_direct = '<div><a href="/buy/mansion/detail/789/">詳細789</a></div>'
    soup_direct = BeautifulSoup(html_direct, "html.parser")
    direct_links = asyncio.run(_collect(parser.parseRootPage(soup_direct)))
    assert len(direct_links) == 1
    assert "detail/789/" in direct_links[0]

    # 7. parseRootPage 都道府県展開クロール (mock _getContent)
    sub_page_html = '<div><a href="/buy/mansion/detail/sub1/">詳細Sub1</a></div>'
    parser._getContent = AsyncMock(return_value=sub_page_html)
    expanded = asyncio.run(_collect(parser.parseRootPage(soup_top)))
    assert len(expanded) >= 1
    assert any("sub1" in u for u in expanded)


def test_daiwa_parser_all_branches():
    """大和ハウスパーサーの従来のページネーションおよび各ページ検出の網羅検証"""
    import asyncio
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()

    # 1. 従来の .pagination a による次ページ
    html_conv = '<div class="pagination"><a href="/buy/mansion/?page=5">次へ</a></div>'
    soup_conv = BeautifulSoup(html_conv, "html.parser")
    assert "page=5" in asyncio.run(parser.parseNextPage(soup_conv))

    # 2. current_page + 1 探索 (aria-current="page")
    html_curr = """
    <div class="pagination">
        <span aria-current="page">2</span>
        <a href="/buy/mansion/?page=2">2</a>
        <a href="/buy/mansion/?page=3">3</a>
    </div>
    """
    soup_curr = BeautifulSoup(html_curr, "html.parser")
    assert "page=3" in asyncio.run(parser.parseNextPage(soup_curr))

    # 3. current_page + 1 探索 (.active)
    html_active = """
    <div class="pagination">
        <span class="active">4</span>
        <a href="/buy/mansion/?page=4">4</a>
        <a href="/buy/mansion/?page=5">5</a>
    </div>
    """
    soup_active = BeautifulSoup(html_active, "html.parser")
    assert "page=5" in asyncio.run(parser.parseNextPage(soup_active))


def test_mitsui_parser_all_branches():
    """三井不動産パーサーの各URL解決・市区町村誘導・エリア展開の網羅検証"""
    import asyncio
    from unittest.mock import MagicMock
    from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiInvestmentParser

    async def _collect(gen):
        return [x async for x in gen]

    parser = MitsuiMansionParser()

    # 1. getRootDestUrl の各パス分岐
    assert parser.getRootDestUrl("https://example.com/item") == "https://example.com/item"
    assert parser.getRootDestUrl("/buy/mansion/p13/") == "https://www.rehouse.co.jp/buy/mansion/p13/"
    assert parser.getRootDestUrl("relative/path") == "https://www.rehouse.co.jp/buy/mansion/relative/path"

    inv_parser = MitsuiInvestmentParser()
    assert inv_parser.getRootDestUrl("prefecture/13/") == "https://www.rehouse.co.jp/buy/tohshi/prefecture/13/"
    assert parser.getRootDestUrl("") == ""

    # 2. getAreaDestUrl
    assert parser.getAreaDestUrl("") == ""
    assert parser.getAreaDestUrl("/buy/mansion/prefecture/13/city/") == ""
    assert parser.getAreaDestUrl("/buy/mansion/prefecture/13/city/13101/") == "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/?limit=1000"
    assert parser.getAreaDestUrl("https://www.rehouse.co.jp/list?foo=bar") == "https://www.rehouse.co.jp/list?foo=bar&limit=1000"

    # 3. parseRootPage 都道府県から市区町村親ページ (/city/) への置換
    async def fake_parse_page_core(resp, xpath_func, url_func):
        yield "https://www.rehouse.co.jp/buy/mansion/prefecture/13/"
        yield "https://www.rehouse.co.jp/buy/mansion/detail/111/"
        yield ""

    parser._parsePageCore = fake_parse_page_core
    root_urls = asyncio.run(_collect(parser.parseRootPage(MagicMock())))
    assert "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/" in root_urls
    assert "https://www.rehouse.co.jp/buy/mansion/detail/111/" in root_urls

    # 4. parseAreaPage
    async def fake_area_core(resp, xpath_func, url_func):
        yield "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/?limit=1000"
        yield ""

    parser._parsePageCore = fake_area_core
    area_urls = asyncio.run(_collect(parser.parseAreaPage(MagicMock())))
    assert len(area_urls) == 1


def test_athome_parser_all_branches():
    """アットホームパーサーの戸建て道路属性パースおよびリスト展開の網羅検証"""
    import asyncio
    from unittest.mock import AsyncMock
    from package.parser.athomeParser import AthomeKodateParser

    async def _collect(gen):
        return [x async for x in gen]

    parser = AthomeKodateParser()

    # 1. 道路情報パース（road_info 優先）
    html_specs1 = """
    <table>
        <tr><th>前面道路</th><td>公道 北東 4.0m</td></tr>
        <tr><th>接道状況</th><td>角地 私道</td></tr>
    </table>
    """
    soup_specs1 = BeautifulSoup(html_specs1, "html.parser")
    item1 = parser.createEntity()
    parser._parsePropertyDetailPage(item1, soup_specs1)
    assert item1.roadDirection == "北東"
    assert item1.roadType == "公道"
    assert item1.roadStructure == "角地"

    # 2. 道路情報パース（setsudou_info フォールバック）
    html_specs2 = """
    <table>
        <tr><th>接道状況</th><td>私道 南西 6.0m 両面道路</td></tr>
    </table>
    """
    soup_specs2 = BeautifulSoup(html_specs2, "html.parser")
    item2 = parser.createEntity()
    parser._parsePropertyDetailPage(item2, soup_specs2)
    assert item2.roadDirection == "南西"
    assert item2.roadType == "私道"
    assert item2.roadStructure == "両面道路"

    # 3. parseRootPage list_links 展開
    html_city_list = """
    <div>
        <a href="/kodate/chuko/tokyo/city-list/">市区町村リスト</a>
    </div>
    """
    sub_page_html = """
    <div>
        <a href="/kodate/1234567890/">物件1</a>
    </div>
    """
    parser._getContent = AsyncMock(return_value=sub_page_html)
    soup_list = BeautifulSoup(html_city_list, "html.parser")
    results = asyncio.run(_collect(parser.parseRootPage(soup_list)))
    assert len(results) >= 1
    assert any("1234567890" in r for r in results)


def test_all_routes_definitions():
    """改修対象となった各社ルート関数のスタートURL定義の網羅検証"""
    from routes.odakyu_routes import get_start_url as odakyu_start
    assert odakyu_start("mansion") == "https://www.odakyu-chukai.com/mansion/list/"
    assert odakyu_start("kodate") == "https://www.odakyu-chukai.com/house/list/"
    assert odakyu_start("tochi") == "https://www.odakyu-chukai.com/land/list/"
    assert odakyu_start("other") == "https://www.odakyu-chukai.com/other/list/"


def test_athome_sequential_pagination_and_host_check():
    """アットホームで番号リンクのみ存在する場合に現在ページの直後(current+1)を選択し、外部ホストを拒絶すること"""
    import asyncio
    from package.parser.athomeParser import AthomeMansionParser

    parser = AthomeMansionParser()

    # 1. 番号リンクのみの場合に最終リンク(10)ではなく現在ページ+1(2)を選択すること
    html_numbers = """
    <div class="pagination">
        <ul class="pagination__list">
            <li class="pagination__item--current">1</li>
            <li><a href="/mansion/chuko/tokyo/list/?page=2">2</a></li>
            <li><a href="/mansion/chuko/tokyo/list/?page=3">3</a></li>
            <li><a href="/mansion/chuko/tokyo/list/?page=10">10</a></li>
        </ul>
    </div>
    """
    soup_numbers = BeautifulSoup(html_numbers, "html.parser")
    next_url = asyncio.run(parser.parseNextPage(soup_numbers))
    assert "page=2" in next_url

    # 2. 外部ホストURLの拒絶検証
    detail_links = set()
    list_links = set()
    ret_url, _ = parser._classify_and_collect_athome_url("https://malicious.com/mansion/12345678/", detail_links, list_links)
    assert ret_url is None
    assert len(detail_links) == 0
    assert len(list_links) == 0


def test_daikyo_pref_expansion_with_existing_details():
    """大京で詳細リンクが存在する場合でも都道府県URLがスキップされずに展開されること"""
    import asyncio
    from unittest.mock import AsyncMock
    from package.parser.daikyoParser import DaikyoMansionParser

    parser = DaikyoMansionParser()
    html_both = """
    <div>
        <a href="/buy/mansion/detail/1001/">注目物件1001</a>
        <a href="/buy/mansion/p13/">東京都一覧</a>
    </div>
    """
    soup_both = BeautifulSoup(html_both, "html.parser")
    parser._getContent = AsyncMock(return_value='<div><a href="/buy/mansion/detail/2001/">都道府県物件2001</a></div>')

    async def _collect():
        return [u async for u in parser.parseRootPage(soup_both)]

    results = asyncio.run(_collect())
    assert any("1001" in u for u in results)
    assert any("2001" in u for u in results)


def test_daiwa_pagination_with_prev_next_svgs():
    """大和ハウスで前・次両方にSVGが存在する場合に前ページではなく次ページ(current+1)を選択すること"""
    import asyncio
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()
    html = """
    <div class="pagination">
        <span class="active">2</span>
        <a href="/buy/search/alist?page=1"><svg><path></path></svg></a>
        <a href="/buy/search/alist?page=1">1</a>
        <a href="/buy/search/alist?page=2">2</a>
        <a href="/buy/search/alist?page=3">3</a>
        <a href="/buy/search/alist?page=3"><svg><path></path></svg></a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert next_url is not None
    assert "page=3" in next_url


def test_tokyu_listing_ended_detection():
    """東急パーサーで掲載終了物件のHTMLが渡された際に早期に ListingEndedException が送出されること"""
    import pytest
    from package.parser.tokyuParser import TokyuTochiParser
    from package.parser.baseParser import ListingEndedException

    parser = TokyuTochiParser()
    html_ended = """
    <html>
        <head><title>東京都港区芝２丁目は掲載終了しました | 東急リバブル</title></head>
        <body>
            <h1>東京都港区芝２丁目は掲載終了しました</h1>
            <div class="message">指定された物件は掲載を終了いたしました。</div>
        </body>
    </html>
    """
    soup_ended = BeautifulSoup(html_ended, "html.parser")
    item = parser.createEntity()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup_ended)


def test_athome_uncovered_branches():
    """athomeパーサーのスキーム検証、テキスト次リンク、空HTML例外処理を検証"""
    import asyncio
    from unittest.mock import AsyncMock
    from package.parser.athomeParser import AthomeMansionParser

    parser = AthomeMansionParser()

    # 1. 不正スキーム (javascript, ftp)
    detail_links = set()
    list_links = set()
    ret_url, _ = parser._classify_and_collect_athome_url("javascript:void(0)", detail_links, list_links)
    assert ret_url is None

    # 2. _find_text_next_tag (クラス指定のない次へリンク)
    html_text_next = '<div><a href="/next?page=2">次へ &gt;</a></div>'
    soup_text = BeautifulSoup(html_text_next, "html.parser")
    next_url = asyncio.run(parser.parseNextPage(soup_text))
    assert "page=2" in next_url

    # 3. _crawl_single_list_page で空HTML
    parser._getContent = AsyncMock(return_value="")
    links, next_page = asyncio.run(parser._crawl_single_list_page("https://www.athome.co.jp/list/", "https://www.athome.co.jp"))
    assert links == []
    assert next_page is None

    # 4. _crawl_single_list_page で例外発生
    parser._getContent = AsyncMock(side_effect=RuntimeError("Network error"))
    links, next_page = asyncio.run(parser._crawl_single_list_page("https://www.athome.co.jp/list/", "https://www.athome.co.jp"))
    assert links == []
    assert next_page is None


def test_daiwa_uncovered_branches():
    """daiwaパーサーのcurrent_page推論(min=2)およびlink_tags判定の各分岐を検証"""
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()

    # 1. current_pageが取得できないが最小ページが2の場合 (現在ページ=1と推論して2を返す)
    html_page2 = """
    <div class="pagination">
        <a href="/buy/search/alist?page=2">2</a>
        <a href="/buy/search/alist?page=3">3</a>
    </div>
    """
    soup_page2 = BeautifulSoup(html_page2, "html.parser")
    next_num = parser._find_next_by_page_number([(2, "/buy/search/alist?page=2", soup_page2.find("a")), (3, "/buy/search/alist?page=3", soup_page2.find_all("a")[1])], soup_page2)
    assert "page=2" in next_num

    # 2. _find_next_by_link_tags で aria-label="前" をスキップし、aria-label="次" を選択すること
    html_aria = """
    <div>
        <a href="/buy/search/alist?page=1" aria-label="前へ">前</a>
        <a href="/buy/search/alist?page=3" aria-label="次へ">次</a>
    </div>
    """
    soup_aria = BeautifulSoup(html_aria, "html.parser")
    tags = soup_aria.find_all("a")
    page_links = [(1, tags[0]["href"], tags[0]), (3, tags[1]["href"], tags[1])]
    next_tag = parser._find_next_by_link_tags(page_links)
    assert "page=3" in next_tag


def test_daiwa_pagination_svg_only_fallback_in_parsenextpage():
    """daiwaParserで現在のページ番号が特定できない場合に_find_next_by_link_tags経由で次ページが取得できること"""
    import asyncio
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()
    html = """
    <div class="pagination">
        <a href="/buy/search/alist?page=1" class="prev"><svg></svg></a>
        <a href="/buy/search/alist?page=3" class="next"><svg></svg></a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert "page=3" in next_url


def test_daiwa_find_next_by_page_number_unmatched():
    """_find_next_by_page_numberで条件に一致しない場合に空文字列を返すこと"""
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()
    html = '<div class="pagination"><a href="/buy/search/alist?page=5">5</a></div>'
    soup = BeautifulSoup(html, "html.parser")
    a_tag = soup.find("a")
    res = parser._find_next_by_page_number([(5, "/buy/search/alist?page=5", a_tag)], soup)
    assert res == ""


def test_daiwa_find_next_by_link_tags_branches():
    """_find_next_by_link_tagsの各条件分岐（前スキップ、次マッチ、クラス文字列／リスト）を検証"""
    from package.parser.daiwaParser import DaiwaMansionParser

    parser = DaiwaMansionParser()

    # 1. 前スキップ（文字列クラス）
    html_prev = '<a href="/prev" class="btn-prev">前</a>'
    soup_prev = BeautifulSoup(html_prev, "html.parser")
    a_prev = soup_prev.find("a")
    assert parser._find_next_by_link_tags([(None, "/prev", a_prev)]) == ""

    # 2. 次マッチ（text="次"）
    html_next_text = '<a href="/next">次へ</a>'
    soup_next = BeautifulSoup(html_next_text, "html.parser")
    a_next = soup_next.find("a")
    assert "/next" in parser._find_next_by_link_tags([(None, "/next", a_next)])

    # 3. 次マッチ（aria-label="next"）
    html_next_aria = '<a href="/next-aria" aria-label="next"></a>'
    soup_aria = BeautifulSoup(html_next_aria, "html.parser")
    a_aria = soup_aria.find("a")
    assert "/next-aria" in parser._find_next_by_link_tags([(None, "/next-aria", a_aria)])


def test_athome_sequential_numbered_tag_branches():
    """_find_sequential_numbered_tagの各分岐（curr_tagなし、非数値、次ページ番号なし）を検証"""
    from package.parser.athomeParser import AthomeMansionParser

    # 1. curr_tagなし -> None
    soup_no_curr = BeautifulSoup('<div class="pagination__list"><a href="/1">1</a></div>', "html.parser")
    assert AthomeMansionParser._find_sequential_numbered_tag(soup_no_curr) is None

    # 2. curr_tagが非数値 -> ValueError -> None
    soup_bad_curr = BeautifulSoup('<div class="pagination__list"><span class="current">ABC</span></div>', "html.parser")
    assert AthomeMansionParser._find_sequential_numbered_tag(soup_bad_curr) is None

    # 3. 次ページ番号(curr+1)のリンクが存在しない -> None
    soup_no_next_num = BeautifulSoup('<div class="pagination__list"><span class="current">1</span><a href="/5">5</a></div>', "html.parser")
    assert AthomeMansionParser._find_sequential_numbered_tag(soup_no_next_num) is None


def test_athome_find_text_next_tag_branches():
    """_find_text_next_tagの各分岐（次、>、»、該当なし）を検証"""
    from package.parser.athomeParser import AthomeMansionParser

    # 1. text=">"
    soup_gt = BeautifulSoup('<div><a href="/gt">&gt;</a></div>', "html.parser")
    assert AthomeMansionParser._find_text_next_tag(soup_gt) is not None

    # 2. text="»"
    soup_raquo = BeautifulSoup('<div><a href="/raquo">&raquo;</a></div>', "html.parser")
    assert AthomeMansionParser._find_text_next_tag(soup_raquo) is not None

    # 3. 該当なし -> None
    soup_none = BeautifulSoup('<div><a href="/other">トップへ</a></div>', "html.parser")
    assert AthomeMansionParser._find_text_next_tag(soup_none) is None


def test_athome_parse_next_page_lxml_input():
    """parseNextPageにlxmlエレメントが渡された場合の変換分岐を検証"""
    import asyncio
    import lxml.html
    from package.parser.athomeParser import AthomeMansionParser

    parser = AthomeMansionParser()
    elem = lxml.html.fromstring('<div><div class="pagination__item--next"><a href="/page2">次</a></div></div>')
    res = asyncio.run(parser.parseNextPage(elem))
    assert "page2" in res


def test_athome_crawl_single_list_page_success():
    """_crawl_single_list_pageで正常にHTMLが取得され詳細リンクおよび次ページが抽出されること"""
    import asyncio
    from unittest.mock import AsyncMock
    from package.parser.athomeParser import AthomeMansionParser

    parser = AthomeMansionParser()
    sample_html = '''
    <html>
        <body>
            <a href="/mansion/12345678/">詳細物件</a>
            <div class="pagination__next"><a href="/list/?page=2">次へ</a></div>
        </body>
    </html>
    '''
    parser._getContent = AsyncMock(return_value=sample_html)
    links, next_page = asyncio.run(parser._crawl_single_list_page("https://www.athome.co.jp/list/", "https://www.athome.co.jp"))
    assert len(links) == 1
    assert "12345678" in links[0]
    assert next_page is not None
    assert "page=2" in next_page



