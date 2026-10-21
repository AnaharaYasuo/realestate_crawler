import pytest
from bs4 import BeautifulSoup
from package.parser.tokyuParser import TokyuTochiParser, TokyuMansionParser, TokyuKodateParser


@pytest.mark.asyncio
async def test_tokyu_tochi_parser_dedup_property_list_cards():
    """1つの物件カード内に複数の <a> タグが存在しても、同一URLは1回のみyieldされること (Issue #1055)"""
    html_content = """
    <div class="propertyListContainer">
        <div class="index-module-scss-module__L5dXvW__propertyCardContents">
            <a href="/tochi/C1326XF14/" class="link1">Title</a>
            <a href="/tochi/C1326XF14/" class="link2">Image</a>
            <a href="/tochi/C1326XF14/" class="link3">Detail Button</a>
        </div>
        <div class="index-module-scss-module__L5dXvW__propertyCardContents">
            <a href="/tochi/C13269G53/" class="link1">Title 2</a>
            <a href="/tochi/C13269G53/" class="link2">Image 2</a>
        </div>
    </div>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parser = TokyuTochiParser()

    items = []
    async for item in parser.parsePropertyListPage(soup):
        items.append(item)

    assert len(items) == 2
    urls = [getattr(it, "url", str(it)) for it in items]
    assert urls == ["https://www.livable.co.jp/tochi/C1326XF14/", "https://www.livable.co.jp/tochi/C13269G53/"]


@pytest.mark.asyncio
async def test_tokyu_parser_dedup_root_page():
    """都道府県選択画面でPC/SP両方のリンクが存在しても、重複排除されて24件のみ抽出されること (Issue #1055)"""
    html_content = """
    <div class="index-module-scss-module__npqgHq__prefecturesListPc">
        <a href="/kounyu/tochi/tokyo/select-area/">東京</a>
        <a href="/kounyu/tochi/kanagawa/select-area/">神奈川</a>
    </div>
    <div class="index-module-scss-module__npqgHq__prefecturesListSp">
        <a href="/kounyu/tochi/tokyo/select-area/">東京</a>
        <a href="/kounyu/tochi/kanagawa/select-area/">神奈川</a>
    </div>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parser = TokyuTochiParser()

    urls = []
    async for u in parser.parseRootPage(soup):
        urls.append(u)

    assert len(urls) == 2
    assert urls == [
        "https://www.livable.co.jp/kounyu/tochi/tokyo/select-area/",
        "https://www.livable.co.jp/kounyu/tochi/kanagawa/select-area/",
    ]


@pytest.mark.asyncio
async def test_tokyu_parser_area_page_city_filter():
    """市区町村選択画面で、正規の市区町村(/a\\d+/)のみを重複なく抽出し、select-townは除外すること (Issue #1055)"""
    html_content = """
    <div>
        <a href="/kounyu/tochi/tokyo/a13121/">世田谷区</a>
        <a href="/kounyu/tochi/tokyo/a13121/select-town/">町名選択</a>
        <a href="/kounyu/tochi/tokyo/a13121/">世田谷区(フッター重複)</a>
        <a href="/kounyu/tochi/tokyo/a13118/">荒川区</a>
    </div>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parser = TokyuTochiParser()

    urls = []
    async for u in parser.parseAreaPage(soup):
        urls.append(u)

    assert len(urls) == 2
    assert urls == [
        "https://www.livable.co.jp/kounyu/tochi/tokyo/a13121/",
        "https://www.livable.co.jp/kounyu/tochi/tokyo/a13118/",
    ]
