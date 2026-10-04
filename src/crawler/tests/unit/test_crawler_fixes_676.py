# -*- coding: utf-8 -*-
"""Issue #676: 0件取得失敗、ページネーション停止、および実行時異常の回帰テスト"""
import pytest
from bs4 import BeautifulSoup

from package.parser.misawaParser import MisawaMansionParser
from package.parser.sekisuiParser import SekisuiMansionParser
from package.parser.odakyuParser import OdakyuMansionParser, OdakyuInvestmentParser
from package.parser.sumirinParser import SumirinInvestmentParser, SumirinMansionParser
from package.parser.daiwaParser import DaiwaMansionParser
from package.parser.homesParser import HomesTochiParser, HomesMansionParser
from package.api.sumifu_investment import ParseSumifuInvestKodateStartAsync
from package.api.nomura_investment import ParseNomuraInvestKodateStartAsync


@pytest.mark.asyncio
async def test_misawa_mansion_parse_next_page_fallback():
    """Misawaマンションで li.next a だけでなく多重フォールバックで次ページURLを抽出できること"""
    parser = MisawaMansionParser()

    # 1. 従来の li.next a パターン
    html1 = '<div><ul class="pager"><li class="next"><a href="/mansion/page/2/">次へ</a></li></ul></div>'
    soup1 = BeautifulSoup(html1, "html.parser")
    next_url1 = await parser.parseNextPage(soup1)
    assert next_url1 == "https://realestate.misawa.co.jp/mansion/page/2/"

    # 2. .pager a[rel='next'] または .next a パターン
    html2 = '<div><div class="pager"><a rel="next" href="/mansion/list/?p=2">次へ &gt;</a></div></div>'
    soup2 = BeautifulSoup(html2, "html.parser")
    next_url2 = await parser.parseNextPage(soup2)
    assert next_url2 == "https://realestate.misawa.co.jp/mansion/list/?p=2"

    # 3. 矢印・次テキストパターン
    html3 = '<div><div class="pagination"><a href="/mansion/page2.html">&gt;</a></div></div>'
    soup3 = BeautifulSoup(html3, "html.parser")
    next_url3 = await parser.parseNextPage(soup3)
    assert next_url3 == "https://realestate.misawa.co.jp/mansion/page2.html"


@pytest.mark.asyncio
async def test_sekisui_mansion_parse_next_page_fallback():
    """Sekisuiマンションで多重セレクター・矢印等で次ページURLを抽出できること"""
    parser = SekisuiMansionParser()

    # 次テキスト
    html1 = '<div><div class="pagination"><a href="/detail/list?page=2">次へ</a></div></div>'
    soup1 = BeautifulSoup(html1, "html.parser")
    next_url1 = await parser.parseNextPage(soup1)
    assert "page=2" in next_url1

    # rel="next"
    html2 = '<div><a rel="next" href="/detail/list?page=3">&gt;</a></div>'
    soup2 = BeautifulSoup(html2, "html.parser")
    next_url2 = await parser.parseNextPage(soup2)
    assert "page=3" in next_url2


@pytest.mark.asyncio
async def test_odakyu_parse_next_page_fallback():
    """Odakyuで次ページリンクを確実に抽出できること"""
    parser = OdakyuMansionParser()

    html1 = '<div class="pagenation-block"><ul class="paging"><li class="next"><a href="/mansion/page_2/">次へ</a></li></ul></div>'
    soup1 = BeautifulSoup(html1, "html.parser")
    next_url1 = await parser.parseNextPage(soup1)
    assert "/mansion/page_2/" in next_url1


def test_sumifu_invest_kodate_start_urls():
    """Sumifu投資用戸建て開始URLが0件判定を招かない有効なURLリストを持つこと"""
    start_api = ParseSumifuInvestKodateStartAsync()
    assert len(start_api.urlList) > 0
    for u in start_api.urlList:
        assert u.startswith("https://www.stepon.co.jp/pro/")


def test_nomura_invest_kodate_start_urls():
    """Nomura投資用戸建て開始URLが有効なURLを持つこと"""
    start_api = ParseNomuraInvestKodateStartAsync()
    assert len(start_api.urlList) > 0
    assert "https://www.nomu.com/pro/" in start_api.urlList[0]


@pytest.mark.asyncio
async def test_sumirin_parse_next_page_fallback():
    """Sumirinでページネーションリンクを抽出できること"""
    parser = SumirinInvestmentParser()
    html = '<div class="pager"><li class="next"><a href="/buy/estate/business/page2/">次へ</a></li></div>'
    soup = BeautifulSoup(html, "html.parser")
    next_url = await parser.parseNextPage(soup)
    assert "page2" in next_url


@pytest.mark.asyncio
async def test_daiwa_parse_next_page_fallback():
    """Daiwaで次ページリンクを抽出できること"""
    parser = DaiwaMansionParser()
    html = '<div class="pager"><a class="next" href="/buy/mansion/page-2/">次へ</a></div>'
    soup = BeautifulSoup(html, "html.parser")
    next_url = await parser.parseNextPage(soup)
    assert "page-2" in next_url
