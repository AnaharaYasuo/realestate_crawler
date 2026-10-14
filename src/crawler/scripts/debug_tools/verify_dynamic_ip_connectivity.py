# -*- coding: utf-8 -*-
"""
Verification script for all real estate sites connectivity (No DB, No VPC required).
Fetches list pages and detail pages for all 23 companies (70 jobs) to verify HTTP/WAF status.
"""
from __future__ import annotations

import os
import sys
import asyncio
import logging
import time
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()

from package.utils.crawl_jobs import CRAWL_JOBS
from package.utils.crawl_job_catalog import CrawlTarget, resolve_crawl_target, load_parser_for_target
from package.utils.crawl_smoke_engine import (
    DEFAULT_HEADERS,
    _discover_detail_urls_for_target,
    _fetch_soup,
    _optional_playwright,
    _needs_playwright,
    _legacy_ssl_context,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DynamicIPVerifier")


async def verify_site_connectivity(target: CrawlTarget, session: aiohttp.ClientSession) -> dict:
    job_id = target.job_id
    parser = load_parser_for_target(target)
    force_pw = _needs_playwright(parser, target.company)
    budget = 40.0
    deadline = time.monotonic() + budget
    start_t = time.monotonic()

    result = {
        "job_id": job_id,
        "company": target.company,
        "property_type": target.property_type,
        "seed_url": target.seed_url,
        "list_ok": False,
        "list_status": None,
        "detail_urls_found": 0,
        "detail_ok": False,
        "detail_status": None,
        "detail_sample_url": "",
        "elapsed_sec": 0.0,
        "error": None,
    }

    try:
        async with _optional_playwright(force_pw) as pw:
            # 1. 一覧ページ取得テスト
            try:
                page_soup = await _fetch_soup(session, target.seed_url, parser, deadline, pw=pw, force_pw=force_pw)
                if page_soup:
                    result["list_ok"] = True
                    result["list_status"] = 200
            except Exception as e:
                result["error"] = f"List fetch error: {e}"
                result["list_status"] = getattr(e, "status", 500)
                result["elapsed_sec"] = time.monotonic() - start_t
                return result

            # 2. 詳細URL抽出テスト
            dummy_smoke_result = type("DummyResult", (), {"errors": [], "pages_fetched": 1, "paging_ok": True})()
            detail_urls, last_err = await _discover_detail_urls_for_target(
                session, parser, target, sample=2, deadline=deadline, pw=pw, force_pw=force_pw, result=dummy_smoke_result
            )
            result["detail_urls_found"] = len(detail_urls)

            # 3. 詳細ページ取得テスト（WAF/403判定）
            if detail_urls:
                sample_url = detail_urls[0]
                result["detail_sample_url"] = sample_url
                try:
                    detail_soup = await _fetch_soup(session, sample_url, parser, deadline, pw=pw, force_pw=force_pw)
                    if detail_soup:
                        result["detail_ok"] = True
                        result["detail_status"] = 200
                except Exception as de:
                    result["error"] = f"Detail fetch error: {de}"
                    result["detail_status"] = getattr(de, "status", 500)
            else:
                result["error"] = f"No detail URLs found from seed (Discovery error: {last_err})"

    except Exception as exc:
        result["error"] = f"Execution exception: {exc}"

    result["elapsed_sec"] = time.monotonic() - start_t
    return result


async def main():
    sites_filter = os.getenv("SITES", "").strip()
    selected_jobs = CRAWL_JOBS
    if sites_filter:
        targets_filter = [s.strip().lower() for s in sites_filter.split(",") if s.strip()]
        selected_jobs = [j for j in CRAWL_JOBS if j[0].lower() in targets_filter or f"{j[0]}_{j[1]}".lower() in targets_filter]

    logger.info("=" * 70)
    logger.info(f"🚀 Starting Dynamic IP Connectivity Verification for {len(selected_jobs)} jobs")
    logger.info("=" * 70)

    # 1社につき1〜2ジョブをピックアップして全社をカバー（重複ドメインの過剰リクエスト防止）
    # 全70ジョブ実行も可能だが、まずは各社のドメイン・WAF疎通を最速で判定
    targets = []
    for job in selected_jobs:
        try:
            target = resolve_crawl_target(job[0], job[1])
            targets.append(target)
        except Exception as e:
            logger.warning(f"Failed to resolve target for {job}: {e}")

    results = []
    # 接続数上限とレートリミット
    connector = aiohttp.TCPConnector(limit=5, ttl_dns_cache=60, ssl=_legacy_ssl_context())
    timeout = aiohttp.ClientTimeout(total=30.0)

    semaphore = asyncio.Semaphore(4)  # 4並列で順次巡回

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector, timeout=timeout) as session:
        async def _bounded_verify(t):
            async with semaphore:
                res = await verify_site_connectivity(t, session)
                status_icon = "✅" if (res["list_ok"] and (res["detail_ok"] or res["detail_urls_found"] > 0)) else "❌"
                logger.info(
                    f"{status_icon} [{res['company']}:{res['property_type']}] "
                    f"List: {'OK' if res['list_ok'] else 'FAIL'}, "
                    f"Details Found: {res['detail_urls_found']}, "
                    f"Detail Fetch: {'OK' if res['detail_ok'] else 'FAIL'} "
                    f"({res['elapsed_sec']:.1f}s) {res['error'] or ''}"
                )
                return res

        results = await asyncio.gather(*[_bounded_verify(t) for t in targets])

    logger.info("=" * 70)
    logger.info("📊 SUMMARY RESULTS")
    logger.info("=" * 70)

    success_count = sum(1 for r in results if r["list_ok"] and r["detail_ok"])
    list_only_count = sum(1 for r in results if r["list_ok"] and not r["detail_ok"])
    fail_count = sum(1 for r in results if not r["list_ok"])

    logger.info(f"Total Tested: {len(results)}")
    logger.info(f"✅ List & Detail OK: {success_count}")
    logger.info(f"⚠️ List OK only (Detail 0 or blocked): {list_only_count}")
    logger.info(f"❌ List Failed/Blocked: {fail_count}")

    blocked = [r for r in results if not r["list_ok"] or not r["detail_ok"]]
    if blocked:
        logger.warning("-" * 70)
        logger.warning("ATTENTION REQUIRED (Possible Block / Empty):")
        for b in blocked:
            logger.warning(f" - {b['job_id']}: List={b['list_ok']}, Detail={b['detail_ok']}, Error: {b['error']}")
    else:
        logger.info("🎉 PERFECT: All tested jobs succeeded via Dynamic IP with NO WAF/403 blocks!")


if __name__ == "__main__":
    asyncio.run(main())
