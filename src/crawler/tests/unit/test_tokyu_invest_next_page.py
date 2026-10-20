import asyncio

from bs4 import BeautifulSoup

from package.parser.tokyuParser import TokyuInvestmentApartmentParser


def _next(html):
    parser = TokyuInvestmentApartmentParser(None)
    return asyncio.run(parser.parseNextPage(BeautifulSoup(html, "html.parser")))


def test_next_page_aria_label_absolute_url():
    html = '<a aria-label="次のページへ" href="https://www.livable.co.jp/x/?page=3"><svg/></a>'
    assert _next(html) == "https://www.livable.co.jp/x/?page=3"


def test_next_page_text_relative_url():
    assert _next('<a href="/x/?page=2">次へ</a>') == "https://www.livable.co.jp/x/?page=2"


def test_next_page_none():
    assert _next('<a href="/x/?page=2">2</a>') == ""
