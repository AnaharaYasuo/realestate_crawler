# -*- coding: utf-8 -*-
"""Issue #340: Sonar CRITICAL 修正箇所のカバレッジ担保"""
import asyncio

import pytest
from bs4 import BeautifulSoup

from package.api.api import require_eval_record
from package.parser.misawaParser import MisawaMansionParser


def test_require_eval_record_raises_when_none():
    with pytest.raises(RuntimeError, match="eval_record is missing"):
        require_eval_record(None, "https://example.com/p/1")


def test_require_eval_record_returns_record():
    sentinel = object()
    assert require_eval_record(sentinel, "https://example.com/p/1") is sentinel


def test_misawa_parse_property_list_skips_missing_anchor_and_href():
    html = """
    <div class="searchList">
      <div class="section"><h3>no link</h3></div>
      <div class="section"><h3><a>empty href</a></h3></div>
      <div class="section"><h3><a href="/detail_ok.html">ok</a></h3></div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MisawaMansionParser(None)
    urls = asyncio.run(_collect(parser.parsePropertyListPage(soup)))
    assert len(urls) == 1
    assert urls[0].endswith("/detail_ok.html")


def test_misawa_parse_next_page_null_safe_branches():
    parser = MisawaMansionParser(None)

    assert asyncio.run(parser.parseNextPage(BeautifulSoup("<ul></ul>", "html.parser"))) == ""

    no_href = BeautifulSoup('<li class="next"><a>next</a></li>', "html.parser")
    assert asyncio.run(parser.parseNextPage(no_href)) == ""

    with_href = BeautifulSoup(
        '<li class="next"><a href="/list?page=2">next</a></li>', "html.parser"
    )
    next_url = asyncio.run(parser.parseNextPage(with_href))
    assert next_url.endswith("/list?page=2")


async def _collect(async_gen):
    return [item async for item in async_gen]
