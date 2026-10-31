# -*- coding: utf-8 -*-
"""
Unit tests for Issue #1167:
1. nomura: Area-based seed URLs (`area_*`) and strict 5-digit municipality filtering in `parseRegionPage` / `parseAreaPage` (excluding 3-4 digit subarea groups and `/id/` detail URLs).
2. athome: Strict municipality list URL filtering in `_is_athome_list_url` and tracking parameter stripping in `_normalize_athome_url`.
3. tokyu: Preventing double `BASE_URL` prefixing on full `https://` URLs and excluding `/grantact/` URLs.
4. differential & url_matcher & homes: Stripping `BKLISTID`, `SEARCHDIV`, `sref` in `UrlMatcher.normalize()`, matching normalized URLs in `_process_differential_chunk`, and correct `tbg[]` property type mapping in `homes_routes.py`.
5. baseParser: Single-card isolation in `_find_card_container` & `_extract_card_price` (returning `None` when a parent container contains multiple distinct property prices).
6. haseko & kenbiya: `haseko_mansion_start` using `/syutoken-buy/mansion/areas/tokyoto-list/` and `KenbiyaParserBase` Playwright stealth fallback on HTTP 403 for real `aiohttp.ClientSession`.
"""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from bs4 import BeautifulSoup
from django.utils import timezone

from package.api.differential import ListItem, filter_differential_items
from package.api.nomura import (
    ParseNomuraKodateRegionFuncAsync,
    ParseNomuraKodateStartAsync,
    ParseNomuraMansionRegionFuncAsync,
    ParseNomuraMansionStartAsync,
    ParseNomuraTochiRegionFuncAsync,
    ParseNomuraTochiStartAsync,
)
from package.parser.athomeParser import (
    AthomeInvestmentApartmentParser,
    AthomeKodateParser,
    AthomeMansionParser,
    AthomeTochiParser,
)
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.kenbiyaParser import KenbiyaMansionParser
from package.parser.nomuraParser import NomuraMansionParser
from package.parser.tokyuParser import TokyuMansionParser
from package.utils.url_matcher import UrlMatcher


def test_nomura_start_urls_use_area_hierarchy():
    """Nomura Start classes must use area_tokyo/kanagawa/saitama/chiba instead of ensen_*."""
    for cls, prefix in [
        (ParseNomuraMansionStartAsync, "/mansion/area_"),
        (ParseNomuraKodateStartAsync, "/house/area_"),
        (ParseNomuraTochiStartAsync, "/land/area_"),
    ]:
        urls = cls.urlList
        assert len(urls) == 4
        assert all(prefix in u for u in urls)
        assert not any("ensen_" in u for u in urls)


@pytest.mark.asyncio
async def test_nomura_region_and_area_filter_out_groups_and_details():
    """Nomura parseRegionPage/parseAreaPage must only yield 5-digit municipality URLs, excluding 3-4 digit groups and /id/ links."""
    html = """
    <div class="c_selection_list">
        <a href="/mansion/area_tokyo/131/">都心・副都心(3桁集計)</a>
        <a href="/mansion/area_tokyo/1311/">千代田・中央・港(4桁集計)</a>
        <a href="/mansion/area_tokyo/13101/">千代田区(5桁市区町村)</a>
        <a href="/mansion/area_tokyo/13201/">八王子市(5桁市区町村)</a>
        <a href="/mansion/id/E0364042/">おすすめ物件詳細</a>
        <a href="/mansion/SearchList/?type=area&s_pref=13">検索リスト</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = NomuraMansionParser()

    region_urls = [u async for u in parser.parseRegionPage(soup)]
    assert region_urls == [
        "https://www.nomu.com/mansion/area_tokyo/13101/",
        "https://www.nomu.com/mansion/area_tokyo/13201/",
    ]

    area_urls = [u async for u in parser.parseAreaPage(soup)]
    assert area_urls == [
        "https://www.nomu.com/mansion/area_tokyo/13101/",
        "https://www.nomu.com/mansion/area_tokyo/13201/",
    ]


def test_athome_list_url_strict_filtering_and_normalization():
    """Athome _is_athome_list_url must only allow target property type & prefecture municipality list URLs."""
    m_parser = AthomeMansionParser()
    # Allowed municipality list URLs
    assert m_parser._is_athome_list_url(
        "/mansion/chuko/tokyo/chiyoda-city/list/",
        "https://www.athome.co.jp/mansion/chuko/tokyo/chiyoda-city/list/",
        True,
    )
    # Disallowed station / line / locate / map / reform / shinchiku / chintai / other pref URLs
    disallowed = [
        "/mansion/chuko/tokyo/akabane-st/list/",
        "/mansion/chuko/tokyo/yamanote-line/list/",
        "/mansion/chuko/tokyo/23ku-locate/list/",
        "/mansion/chuko/tokyo/map/list/",
        "/mansion/chuko/tokyo/line/",
        "/mansion/chuko/tokyo/rosen_map/",
        "/mansion/chuko/reform-renovation/tokyo/city/",
        "/mansion/shinchiku/tokyo/list/",
        "/chintai/tokyo/city/",
        "/buyall/",
        "/mansion/chuko/fukuoka/fukuoka-city/list/",
        "/kodate/chuko/tokyo/chiyoda-city/list/",
    ]
    for path in disallowed:
        assert not m_parser._is_athome_list_url(
            path, f"https://www.athome.co.jp{path}", True
        ), f"Should reject {path}"

    # Normalization strips tracking queries (DOWN, BKLISTID, SEARCHDIV, sref)
    norm = m_parser._normalize_athome_url(
        "/mansion/6991461284/?DOWN=1&BKLISTID=001LPC&SEARCHDIV=1&sref=list_simple",
        "https://www.athome.co.jp",
    )
    assert norm == "https://www.athome.co.jp/mansion/6991461284/"


def test_tokyu_dest_url_no_double_prefix_and_excludes_grantact():
    """Tokyu getPropertyListDestUrl/getRootDestUrl/getAreaDestUrl must not double-prefix https:// and must skip /grantact/."""
    parser = TokyuMansionParser()
    assert (
        parser.getPropertyListDestUrl("https://www.livable.co.jp/mansion/C12345/")
        == "https://www.livable.co.jp/mansion/C12345/"
    )
    assert (
        parser.getPropertyListDestUrl("/mansion/C12345/")
        == "https://www.livable.co.jp/mansion/C12345/"
    )
    assert (
        parser.getPropertyListDestUrl(
            "https://www.livable.co.jp/grantact/detail/GA2507001"
        )
        == ""
    )


@pytest.mark.asyncio
async def test_url_matcher_and_differential_crawl_matching():
    """UrlMatcher and filter_differential_items must match URLs despite tracking queries and trailing slashes."""
    raw_url = "https://www.athome.co.jp/mansion/6991461284/?DOWN=1&BKLISTID=001LPC&SEARCHDIV=1&sref=list_simple"
    db_url = "https://www.athome.co.jp/mansion/6991461284"
    assert UrlMatcher.is_same_url(raw_url, db_url)
    assert UrlMatcher.normalize(raw_url) == "https://www.athome.co.jp/mansion/6991461284/"

    now = timezone.now()
    mock_model = MagicMock()
    mock_model.__name__ = "AthomeMansion"
    mock_qs = MagicMock()
    mock_qs.values.return_value = [
        {
            "pageUrl": db_url,
            "price": 54800000,
            "updateDateTime": now - timedelta(days=1),
            "inputDateTime": now - timedelta(days=5),
        }
    ]
    mock_qs.update.return_value = 1
    mock_model.objects.filter.return_value = mock_qs

    items = [ListItem(url=raw_url, price=54800000)]
    to_fetch, to_skip = await filter_differential_items(
        items=items, model_class=mock_model, ttl_days=30, force_full=False, enabled=True
    )
    assert to_fetch == []
    assert len(to_skip) == 1


def test_card_price_extraction_rejects_multi_property_wrapper():
    """ParserBase._extract_card_price must return None when the matched container holds multiple distinct property prices."""
    html = """
    <div class="bukken-list">
        <div class="unit-entry">
            <a href="/mansion/id/1/">物件1</a>
            <span class="price">4,100万円</span>
        </div>
        <div class="unit-entry">
            <a href="/mansion/id/2/">物件2</a>
            <span class="price">5,980万円</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = NomuraMansionParser()
    # Neither .unit-entry matches _CARD_KEYWORDS ("entry" is not in _CARD_KEYWORDS),
    # so climbing to .bukken-list sees 2 distinct prices and must return None rather than 41000000!
    links = soup.select("a")
    assert parser._extract_card_price(links[1]) is None


def test_homes_routes_tbg_mapping():
    """homes_routes.py must map tbg[]=1 (mansion), tbg[]=2 (invest_apartment), tbg[]=8 (kodate), tbg[]=5 (tochi)."""
    import routes.homes_routes as hr

    with patch.object(hr.ParseHomesMansionStartAsync, "main", return_value=("finish", 200)) as m_main, \
         patch.object(hr.ParseHomesInvestApartmentStartAsync, "main", return_value=("finish", 200)) as ia_main, \
         patch.object(hr.ParseHomesKodateStartAsync, "main", return_value=("finish", 200)) as k_main, \
         patch.object(hr.ParseHomesTochiStartAsync, "main", return_value=("finish", 200)) as t_main:
        hr.homes_mansion_start()
        hr.homes_invest_apartment_start()
        hr.homes_kodate_start()
        hr.homes_tochi_start()

        assert "tbg[]=1" in m_main.call_args[0][0]
        assert "tbg[]=2" in ia_main.call_args[0][0]
        assert "tbg[]=8" in k_main.call_args[0][0]
        assert "tbg[]=5" in t_main.call_args[0][0]


def test_haseko_start_route_uses_tokyoto_list():
    """haseko_mansion_start must use /syutoken-buy/mansion/areas/tokyoto-list/."""
    import routes.mid_brokers_routes as mbr

    with patch.object(mbr.ParseHasekoMansionStartAsync, "main", return_value=("finish", 200)) as h_main:
        mbr.haseko_mansion_start()
        assert h_main.call_args[0][0] == "https://www.haseko-chukai.com/syutoken-buy/mansion/areas/tokyoto-list/"


@pytest.mark.asyncio
async def test_kenbiya_403_playwright_fallback_on_real_client_session():
    """KenbiyaParserBase._getContent must fall back to _fetch_with_playwright when HTTP 403 occurs on an aiohttp.ClientSession."""
    parser = KenbiyaMansionParser()
    mock_resp = MagicMock()
    mock_resp.status = 403

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(
        parser, "_fetch_with_playwright", new=AsyncMock(return_value=b"<html><body>Kenbiya OK</body></html>")
    ) as mock_pw:
        content = await parser._getContent(mock_session, "https://www.kenbiya.com/pp1/s/tokyo/")
        assert content == b"<html><body>Kenbiya OK</body></html>"
        mock_pw.assert_awaited_once_with("https://www.kenbiya.com/pp1/s/tokyo/")
