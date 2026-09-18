# -*- coding: utf-8 -*-
import pytest
from package.parser.sumifuParser import SumifuMansionParser
from package.models.sumifu import SumifuMansion
from bs4 import BeautifulSoup


def test_clean_parsed_item_sanitizes_none_kaisu_str():
    """Test that clean_parsed_item sanitizes None kaisuStr to empty string to avoid IntegrityError."""
    parser = SumifuMansionParser()
    item = SumifuMansion()
    item.kaisuStr = None
    item.address = "東京都新宿区"
    item.price = 50000000

    cleaned = parser.clean_parsed_item(item)
    assert cleaned.kaisuStr == "", "kaisuStr was None, expected empty string"


def test_sumifu_dest_url_double_scheme_guard():
    """Test that SumifuParser does not produce invalid URLs like www.stepon.co.jphttps:443."""
    parser = SumifuMansionParser()

    # Relative URL
    rel_url = "/mansion/tokai/"
    assert parser.getRegionDestUrl(rel_url) == "https://www.stepon.co.jp/mansion/tokai/"

    # Absolute URL (already has scheme and domain)
    abs_url = "https://www.stepon.co.jp/mansion/tokai/"
    assert parser.getRegionDestUrl(abs_url) == "https://www.stepon.co.jp/mansion/tokai/"

    # Area URL relative
    rel_area = "/mansion/tokai/aichi/"
    assert parser.getAreaDestUrl(rel_area) == "https://www.stepon.co.jp/mansion/tokai/aichi/?limit=1000&mode=2"

    # Area URL absolute
    abs_area = "https://www.stepon.co.jp/mansion/tokai/aichi/"
    assert parser.getAreaDestUrl(abs_area) == "https://www.stepon.co.jp/mansion/tokai/aichi/?limit=1000&mode=2"


@pytest.mark.asyncio
async def test_sumifu_next_page_urljoin():
    """Test that getPropertyListNextPageUrl properly resolves next page URL without duplicating domain."""
    parser = SumifuMansionParser()

    # Relative next link
    html_rel = '<html><body><a class="next" href="/mansion/tokai/page2/">次へ</a></body></html>'
    soup_rel = BeautifulSoup(html_rel, "html.parser")
    next_url = await parser.getPropertyListNextPageUrl(soup_rel)
    assert next_url == "https://www.stepon.co.jp/mansion/tokai/page2/"

    # Absolute next link
    html_abs = '<html><body><a class="next" href="https://www.stepon.co.jp/mansion/tokai/page2/">次へ</a></body></html>'
    soup_abs = BeautifulSoup(html_abs, "html.parser")
    next_url_abs = await parser.getPropertyListNextPageUrl(soup_abs)
    assert next_url_abs == "https://www.stepon.co.jp/mansion/tokai/page2/"
