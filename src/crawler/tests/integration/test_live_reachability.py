# -*- coding: utf-8 -*-
"""
全不動産サイト ライブ到達性 & 全フィールド動的パース検証統合テスト
(Live Reachability & Full-Field Parsing Integration Test)
"""

import pytest
import asyncio
import aiohttp
import urllib.parse
import re
import ssl
from bs4 import BeautifulSoup

import time

from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi
from package.models.misawa import MisawaMansion, MisawaKodate
from package.models.smtrc import SmtrcMansion
from package.models.keio import KeioMansion
from package.models.rearie import RearieMansion

from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser, MitsuiTochiParser
from package.parser.tokyuParser import TokyuMansionParser, TokyuKodateParser, TokyuTochiParser
from package.parser.misawaParser import MisawaMansionParser, MisawaKodateParser
from package.parser.smtrcParser import SmtrcMansionParser
from package.parser.keioParser import KeioMansionParser
from package.parser.rearieParser import RearieMansionParser, RearieParser
from package.parser.baseParser import ListingEndedException

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

TARGET_SITES = [
    # --- 三井のリハウス (Mitsui) ---
    {
        "site": "mitsui_mansion",
        "list_url": "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/",
        "base_url": "https://www.rehouse.co.jp",
        "detail_pattern": r"/buy/mansion/bkdetail/",
        "parser_cls": MitsuiMansionParser,
        "model_cls": MitsuiMansion,
        "encoding": "utf-8",
    },
    {
        "site": "mitsui_kodate",
        "list_url": "https://www.rehouse.co.jp/buy/kodate/prefecture/13/city/13101/",
        "base_url": "https://www.rehouse.co.jp",
        "detail_pattern": r"/buy/kodate/bkdetail/",
        "parser_cls": MitsuiKodateParser,
        "model_cls": MitsuiKodate,
        "encoding": "utf-8",
    },
    {
        "site": "mitsui_tochi",
        "list_url": "https://www.rehouse.co.jp/buy/tochi/prefecture/13/city/13101/",
        "base_url": "https://www.rehouse.co.jp",
        "detail_pattern": r"/buy/tochi/bkdetail/",
        "parser_cls": MitsuiTochiParser,
        "model_cls": MitsuiTochi,
        "encoding": "utf-8",
    },
    # --- 東急リバブル (Tokyu) ---
    {
        "site": "tokyu_mansion",
        "list_url": "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13101/",
        "base_url": "https://www.livable.co.jp",
        "detail_pattern": r"/mansion/C[A-Z0-9]+",
        "parser_cls": TokyuMansionParser,
        "model_cls": TokyuMansion,
        "encoding": "utf-8",
    },
    {
        "site": "tokyu_kodate",
        "list_url": "https://www.livable.co.jp/kounyu/kodate/tokyo/a13101/",
        "base_url": "https://www.livable.co.jp",
        "detail_pattern": r"/kodate/C[A-Z0-9]+",
        "parser_cls": TokyuKodateParser,
        "model_cls": TokyuKodate,
        "encoding": "utf-8",
    },
    {
        "site": "tokyu_tochi",
        "list_url": "https://www.livable.co.jp/kounyu/tochi/tokyo/a13103/",
        "base_url": "https://www.livable.co.jp",
        "detail_pattern": r"/tochi/C[A-Z0-9]+",
        "parser_cls": TokyuTochiParser,
        "model_cls": TokyuTochi,
        "encoding": "utf-8",
    },
    # --- ミサワホーム (Misawa) ---
    {
        "site": "misawa_mansion",
        "list_url": "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=9",
        "base_url": "https://realestate.misawa.co.jp",
        "detail_pattern": r"/detail/",
        "parser_cls": MisawaMansionParser,
        "model_cls": MisawaMansion,
        "encoding": "utf-8",
        "ssl_fix": True,
    },
    {
        "site": "misawa_kodate",
        "list_url": "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=10",
        "base_url": "https://realestate.misawa.co.jp",
        "detail_pattern": r"/detail/",
        "parser_cls": MisawaKodateParser,
        "model_cls": MisawaKodate,
        "encoding": "utf-8",
        "ssl_fix": True,
    },
    # --- 三井住友トラスト (SMTRC) ---
    {
        "site": "smtrc_mansion",
        "list_url": "https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1",
        "base_url": "https://smtrc.jp",
        "detail_pattern": r"/(buy/detail|detail|bukken)/",
        "parser_cls": SmtrcMansionParser,
        "model_cls": SmtrcMansion,
        "encoding": "utf-8",
    },
    # --- 京王不動産 (Keio) ---
    {
        "site": "keio_mansion",
        "list_url": "https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=30&page_num=1&pref=13&boshu_kind_summary_code%5B%5D=1",
        "base_url": "https://chukai.keiofudosan.co.jp",
        "detail_pattern": r"/sale/\d+",
        "parser_cls": KeioMansionParser,
        "model_cls": KeioMansion,
        "encoding": "utf-8",
        "ssl_context": True,
    },
    # --- レアリエ (Rearie) ---
    {
        "site": "rearie_mansion",
        "list_url": "https://phfudousan.repros.jp/api/v2/kubunList/?key=32df8d8a-58fb-5d59-ab6a-6e6c09239add",
        "base_url": "https://phfudousan.repros.jp",
        "detail_pattern": r"kubunDetail",
        "parser_cls": RearieMansionParser,
        "model_cls": RearieMansion,
        "encoding": "utf-8",
    },
]

def assert_full_model_fields(item, model_cls, site_name: str):
    """
    検証処理: 必須項目（propertyName, price, address）の非空検証と、
    モデル定義フィールド全体の抽出カバー率（20%以上）を検証する。
    """
    # 1. 必須フィールドアサーション
    assert getattr(item, 'propertyName', None) is not None, f"[{site_name}] propertyName is None!"
    assert getattr(item, 'price', None) is not None, f"[{site_name}] price is None!"
    assert getattr(item, 'address', None) is not None, f"[{site_name}] address is None!"

    # 2. モデル定義フィールド全体のカバー率検証
    model_fields = [f.name for f in model_cls._meta.fields if f.name not in ('id', 'created_at', 'updated_at', 'inputDate')]
    populated_fields = []
    missing_fields = []

    for f_name in model_fields:
        val = getattr(item, f_name, None)
        if val is not None and val != "":
            populated_fields.append(f_name)
        else:
            missing_fields.append(f_name)

    coverage_ratio = len(populated_fields) / len(model_fields) if model_fields else 0.0
    print(f"\n[{site_name}] Field Coverage: {len(populated_fields)}/{len(model_fields)} ({coverage_ratio*100:.1f}%)")
    print(f"[{site_name}] Populated Fields ({len(populated_fields)}): {populated_fields}")
    if missing_fields:
        print(f"[{site_name}] MISSING FIELDS ({len(missing_fields)}): {missing_fields}")
    
    # 3. 最低カバー率（20%以上）アサーション
    assert coverage_ratio >= 0.20, (
        f"[{site_name}] FIELD COVERAGE TOO LOW!\n"
        f"Coverage ratio was {coverage_ratio*100:.1f}% ({len(populated_fields)}/{len(model_fields)} fields populated).\n"
        f"Missing fields: {missing_fields}"
    )


async def run_single_site_test(target: dict):
    site = target["site"]
    list_url = target["list_url"]
    base_url = target["base_url"]
    pattern = target["detail_pattern"]
    parser_cls = target["parser_cls"]
    model_cls = target["model_cls"]
    encoding = target.get("encoding", "utf-8")

    ssl_val = False
    if target.get("ssl_context"):
        ssl_val = ssl.create_default_context()
    elif target.get("ssl_fix"):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        ssl_val = ssl_context

    connector = aiohttp.TCPConnector(ssl=ssl_val)
    timeout = aiohttp.ClientTimeout(total=20)

    async with aiohttp.ClientSession(headers=HEADERS, connector=connector, timeout=timeout) as session:
        req_headers = dict(HEADERS)
        if "wp-json" in list_url:
            req_headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
            req_headers['X-Requested-With'] = 'XMLHttpRequest'
            req_headers['Referer'] = 'https://chukai.keiofudosan.co.jp/sale/search/area/pref_13/'
        elif "phfudousan.repros.jp" in list_url:
            req_headers.update(RearieParser.REPROS_HEADERS)

        async with session.get(list_url, headers=req_headers, ssl=ssl_val) as resp:
            assert resp.status == 200, f"[{site}] Failed to access list URL: {list_url} (HTTP {resp.status})"
            content_type = resp.headers.get("Content-Type", "")
            if "phfudousan.repros.jp" in list_url:
                res_json = await resp.json()
                items = res_json.get("data", {}).get("list", [])
                detail_links = [
                    f"https://phfudousan.repros.jp/api/v1/kubunDetail/?id={itm['id']}&key={RearieParser.REPROS_KEY}"
                    for itm in items if "id" in itm
                ]
            elif "json" in content_type or "wp-json" in list_url:
                data = await resp.json()
                html = data.get("html", "")
                soup = BeautifulSoup(html, "html.parser")
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                detail_links = []
                for href in all_links:
                    full_url = urllib.parse.urljoin(base_url, href)
                    if re.search(pattern, full_url) and full_url not in detail_links:
                        detail_links.append(full_url)
            else:
                raw_bytes = await resp.read()
                html = raw_bytes.decode(encoding, errors='replace')
                soup = BeautifulSoup(html, "html.parser")
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                detail_links = []
                for href in all_links:
                    full_url = urllib.parse.urljoin(base_url, href)
                    if re.search(pattern, full_url) and full_url not in detail_links:
                        detail_links.append(full_url)

        print(f"[{site}] Extracted Detail Links: {len(detail_links)} links found.")
        assert len(detail_links) > 0, f"[{site}] ZERO DETAIL LINKS EXTRACTED from {list_url}! Selector/Route needs update."

        # 二段階動的検証（Phase 1: 先頭3件スモーク ➔ Phase 2: 最大20件へ自動拡張）
        sample_count = min(len(detail_links), 20)
        test_sample_urls = detail_links[:sample_count]
        parser = parser_cls()

        for idx, detail_url in enumerate(test_sample_urls, 1):
            if "phfudousan.repros.jp" in detail_url:
                start_parse = time.perf_counter()
                cleaned_item = await parser.parsePropertyDetailPage(session, detail_url)
            else:
                async with session.get(detail_url, ssl=ssl_val) as d_resp:
                    if d_resp.status in (403, 404):
                        print(f" [{site}] Detail URL HTTP {d_resp.status} (Skipped expired page): {detail_url}")
                        continue
                    assert d_resp.status == 200, f"[{site}] Detail page HTTP {d_resp.status}: {detail_url}"
                    d_bytes = await d_resp.read()
                    d_html = d_bytes.decode(encoding, errors='replace')

                # 純パース時間計測 & SLA アサーション (ネットワーク待機時間を除外)
                start_parse = time.perf_counter()
                d_soup = BeautifulSoup(d_html, "html.parser")
                item = parser.createEntity()
                try:
                    parsed_item = parser._parsePropertyDetailPage(item, d_soup)
                    cleaned_item = parser.clean_parsed_item(parsed_item)
                except ListingEndedException as e:
                    print(f" [{site}] Skipped listing ended page: {detail_url} ({e})")
                    continue

            parse_ms = (time.perf_counter() - start_parse) * 1000.0
            print(f" [{site}] Pure parse time: {parse_ms:.2f}ms")
            assert parse_ms < 10000.0, f"[{site}] Pure parse time exceeded 10,000ms SLA: {parse_ms:.2f}ms"

            # 全フィールド検証
            assert_full_model_fields(cleaned_item, model_cls, site)
            print(f" [{site}] Detail #{idx} SUCCESS: '{cleaned_item.propertyName}' - {cleaned_item.priceStr}")


@pytest.mark.live
@pytest.mark.parametrize("target", TARGET_SITES, ids=[t["site"] for t in TARGET_SITES])
def test_site_live_reachability_and_full_parsing(target: dict):
    """
    各不動産サイトのスタート/一覧URLから実サイトの詳細URLを抽出し、
    先頭20件の詳細ページをパースして全フィールド値・SLA処理時間をチェックする統合テスト
    """
    asyncio.run(run_single_site_test(target))

