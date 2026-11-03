import pytest
from bs4 import BeautifulSoup
from package.parser.nomuraParser import NomuraMansionParser, NomuraParser


@pytest.mark.asyncio
async def test_nomura_property_list_strict_and_deduplication():
    parser = NomuraMansionParser()

    # HTML containing standard item_title links, recommendation cards outside item_title, and duplicate links
    sample_html = """
    <div class="search_result_list">
        <!-- Valid property cards -->
        <div class="result_card">
            <h3 class="item_title">
                <a href="/mansion/id/EB2X4001/">パークタワー勝どきサウス</a>
            </h3>
            <span class="price">12,800万円</span>
        </div>
        <div class="result_card">
            <h3 class="item_title">
                <a href="/mansion/id/EB2X4002/">ブランズタワー芝浦</a>
            </h3>
            <span class="price">15,000万円</span>
        </div>

        <!-- Duplicate link on the same page -->
        <div class="result_card">
            <h3 class="item_title">
                <a href="/mansion/id/EB2X4001/">パークタワー勝どきサウス (duplicate card)</a>
            </h3>
            <span class="price">12,800万円</span>
        </div>

        <!-- Recommendation / feature section outside item_title -->
        <div class="module_link_recommend">
            <a href="/mansion/id/EB2X9999/">おすすめ：タワーマンション特集物件</a>
        </div>
    </div>
    """

    soup = BeautifulSoup(sample_html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]

    # Should only extract 2 distinct items from .item_title, ignoring duplicates and recommend links
    urls = [item.url for item in items]
    assert len(urls) == 2
    assert "https://www.nomu.com/mansion/id/EB2X4001/" in urls
    assert "https://www.nomu.com/mansion/id/EB2X4002/" in urls
    assert not any("EB2X9999" in u for u in urls)


@pytest.mark.asyncio
async def test_nomura_region_page_strict_pref_filtering():
    parser = NomuraMansionParser()

    # Sample region page for tokyo containing tokyo municipalities in .searchSelectTabFrame,
    # and other prefecture recommendations in .module_link_recommend
    sample_region_html = """
    <div class="searchSelectTabFrame">
        <ul>
            <li><a href="/mansion/area_tokyo/13101/">千代田区</a></li>
            <li><a href="/mansion/area_tokyo/13102/">中央区</a></li>
            <li><a href="/mansion/area_tokyo/13103/">港区</a></li>
        </ul>
    </div>
    <div class="module_link_recommend">
        <h4>他エリアのおすすめ</h4>
        <ul>
            <li><a href="/mansion/area_kanagawa/14101/">横浜市鶴見区</a></li>
            <li><a href="/mansion/area_saitama/11101/">さいたま市西区</a></li>
            <li><a href="/mansion/area_chiba/12101/">千葉市中央区</a></li>
        </ul>
    </div>
    """

    soup = BeautifulSoup(sample_region_html, "html.parser")
    current_url = "https://www.nomu.com/mansion/area_tokyo/"

    # Parse region page passing current_url
    region_urls = [url async for url in parser.parseRegionPage(soup, current_url=current_url)]

    assert len(region_urls) == 3
    assert all("area_tokyo" in u for u in region_urls)
    assert not any("kanagawa" in u or "saitama" in u or "chiba" in u for u in region_urls)


def test_extract_filtered_area_urls_prefecture_isolation():
    elements = [
        {"href": "/mansion/area_tokyo/13101/"},
        {"href": "/mansion/area_tokyo/13102/"},
        {"href": "/mansion/area_kanagawa/14101/"},
        {"href": "/mansion/area_saitama/11101/"},
        {"href": "/mansion/tokyo/special/"},
        {"href": "/mansion/id/EB2X4001/"},
    ]

    class FakeEl:
        def __init__(self, href):
            self.href = href
        def get(self, attr):
            return self.href if attr == "href" else None

    fake_elements = [FakeEl(e["href"]) for e in elements]

    # Test filtering for tokyo
    tokyo_urls = NomuraParser._extract_filtered_area_urls(fake_elements, target_pref="tokyo")
    assert len(tokyo_urls) == 2
    assert "https://www.nomu.com/mansion/area_tokyo/13101/" in tokyo_urls
    assert "https://www.nomu.com/mansion/area_tokyo/13102/" in tokyo_urls

    # Test filtering for kanagawa
    kanagawa_urls = NomuraParser._extract_filtered_area_urls(fake_elements, target_pref="kanagawa")
    assert len(kanagawa_urls) == 1
    assert "https://www.nomu.com/mansion/area_kanagawa/14101/" in kanagawa_urls
