# -*- coding: utf-8 -*-
"""#904: sumifu(stepon) 一覧は30件/ページ。実マークアップの「次の30件へ」を辿れること。"""
import pytest
from bs4 import BeautifulSoup

from package.parser.sumifuParser import SumifuKodateParser, SumifuMansionParser, SumifuTochiParser

PAGE1 = (
    '<div class="pagination"><div class="pagination__prev" id="page_link_head"></div>'
    '<ol class="pagination__buttons" id="page_link">'
    '<li><a class="pagination-button is-current">1</a></li>'
    '<li><a href="/kodate/area_13/list_13_112/30_2/" class="pagination-button">2</a></li></ol>'
    '<div class="pagination__next" id="page_link_tail">'
    '<a href="/kodate/area_13/list_13_112/30_2/" class="pagination-button pagination-button--next">次の30件へ</a>'
    '</div></div>'
)
LAST_PAGE = (
    '<div class="pagination"><ol class="pagination__buttons">'
    '<li><a href="/kodate/area_13/list_13_112/" class="pagination-button">1</a></li>'
    '<li><a class="pagination-button is-current">2</a></li></ol></div>'
)


@pytest.mark.asyncio
@pytest.mark.parametrize("parser_cls", [SumifuKodateParser, SumifuMansionParser, SumifuTochiParser])
async def test_next_30_link_followed(parser_cls):
    parser = parser_cls()
    url = await parser.getPropertyListNextPageUrl(BeautifulSoup(PAGE1, "html.parser"))
    assert url == "https://www.stepon.co.jp/kodate/area_13/list_13_112/30_2/"


@pytest.mark.asyncio
async def test_last_page_stops():
    parser = SumifuKodateParser()
    assert await parser.getPropertyListNextPageUrl(BeautifulSoup(LAST_PAGE, "html.parser")) is None
