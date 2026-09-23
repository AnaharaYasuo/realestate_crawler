# -*- coding: utf-8 -*-
import logging
import re
from typing import List, Optional
from xml.etree import ElementTree as ET

import aiohttp
from playwright.async_api import async_playwright

# Official detail sitemaps (robots.txt → sitemap_all.xml). WAF-safe discovery.
_SITEMAP_BY_KIND = {
    "house": ("https://www.mizuho-re.co.jp/sitemap_detail_house.xml",),
    "kodate": ("https://www.mizuho-re.co.jp/sitemap_detail_house.xml",),
    "mansion": ("https://www.mizuho-re.co.jp/sitemap_detail_mansion.xml",),
    "tochi": ("https://www.mizuho-re.co.jp/sitemap_detail_land.xml",),
    "land": ("https://www.mizuho-re.co.jp/sitemap_detail_land.xml",),
    "investment": (
        "https://www.mizuho-re.co.jp/sitemap_detail_kubun.xml",
        "https://www.mizuho-re.co.jp/sitemap_detail_whole.xml",
    ),
}


def infer_mizuho_sitemap_kind(url_or_type: str) -> str:
    """Map list URL or property_type to sitemap kind."""
    text = (url_or_type or "").lower()
    if "invest" in text:
        return "investment"
    if "house" in text or "kodate" in text:
        return "house"
    if "tochi" in text or "land" in text:
        return "land"
    if "mansion" in text:
        return "mansion"
    return "mansion"


def parse_mizuho_sitemap_locs(xml_text: str) -> List[str]:
    """Extract <loc> URLs from a Mizuho detail sitemap document."""
    if not xml_text:
        return []
    locs: List[str] = []
    try:
        root = ET.fromstring(xml_text)
        for el in root.iter():
            if el.tag.endswith("loc") and el.text:
                url = el.text.strip()
                if "/property/" in url:
                    locs.append(url if url.endswith("/") else url + "/")
    except ET.ParseError:
        locs = re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", xml_text)
        locs = [
            (u if u.endswith("/") else u + "/")
            for u in locs
            if "/property/" in u
        ]
    seen = set()
    out: List[str] = []
    for u in locs:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def get_mizuho_links_from_sitemap(
    kind_or_url: str, limit: int = 40
) -> List[str]:
    """Fetch official detail sitemap(s) for the property kind (aiohttp, no PW)."""
    kind = infer_mizuho_sitemap_kind(kind_or_url)
    sitemap_urls = _SITEMAP_BY_KIND.get(kind, _SITEMAP_BY_KIND["mansion"])
    collected: List[str] = []
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for sm_url in sitemap_urls:
                if len(collected) >= limit:
                    break
                try:
                    async with session.get(sm_url, ssl=True) as resp:
                        if resp.status != 200:
                            logging.warning(
                                "MizuhoBypass: sitemap HTTP %s for %s",
                                resp.status,
                                sm_url,
                            )
                            continue
                        text = await resp.text(errors="replace")
                except Exception as exc:  # noqa: BLE001
                    logging.warning(
                        "MizuhoBypass: sitemap fetch failed %s: %s", sm_url, exc
                    )
                    continue
                for loc in parse_mizuho_sitemap_locs(text):
                    if loc not in collected:
                        collected.append(loc)
                    if len(collected) >= limit:
                        break
    except Exception as exc:  # noqa: BLE001
        logging.warning("MizuhoBypass: sitemap session failed: %s", exc)
        return []
    logging.info(
        "MizuhoBypass: sitemap kind=%s yielded %d links", kind, len(collected)
    )
    return collected[:limit]


async def _extract_links_from_page(page, response) -> list:
    title = await page.title()
    logging.info(
        f"MizuhoBypass: Page loaded. Title: {title}, "
        f"Status: {response.status if response else 'None'}"
    )

    if "403" in title or (response and response.status == 403):
        logging.error("MizuhoBypass: Got blocked with 403!")
        return []

    hrefs = await page.evaluate("""() => {
        const links = [];
        document.querySelectorAll('a').forEach(a => {
            const href = a.getAttribute('href');
            if (!href) return;
            const h = href.toLowerCase();
            if (
                h.includes('/property/') ||
                h.includes('/buyers/detail/') ||
                h.includes('/investors/detail/') ||
                h.includes('/buyers/bukken/') ||
                /\\/buyers\\/[a-z0-9_-]*\\d{4,}/.test(h)
            ) {
                links.push(href);
            }
        });
        return links;
    }""")

    base_url = "https://www.mizuho-re.co.jp"
    links = []
    for href in hrefs:
        if href.startswith("/"):
            full_url = base_url + href
        elif href.startswith("http"):
            full_url = href
        else:
            continue
        if full_url not in links:
            links.append(full_url)

    logging.info(
        f"MizuhoBypass: Successfully extracted {len(links)} detailed links via Playwright."
    )
    return links


async def get_mizuho_links(url: str, limit: Optional[int] = None) -> list:
    """一覧が WAF で取れない場合に備え、公式 sitemap を先に試し、次に Playwright 一覧を試す。

    limit=None: production-scale sitemap fetch. Smoke callers may pass a small limit.
    """
    logging.info(f"MizuhoBypass: Initializing discovery for URL: {url}")
    kind = infer_mizuho_sitemap_kind(url)
    sitemap_limit = max(1, int(limit)) if limit is not None else 500
    sitemap_links = await get_mizuho_links_from_sitemap(kind, limit=sitemap_limit)
    if sitemap_links:
        logging.info(
            "MizuhoBypass: Using official sitemap (%d links) for kind=%s",
            len(sitemap_links),
            kind,
        )
        return sitemap_links
    logging.warning(
        "MizuhoBypass: sitemap empty for kind=%s; falling back to Playwright list",
        kind,
    )
    links = await _get_mizuho_links_once(url)
    if limit is not None:
        return links[: max(1, int(limit))]
    return links


async def _get_mizuho_links_once(url: str) -> list:
    links = []
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        "--headless=new",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                    viewport={"width": 1280, "height": 800},
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ja-JP', 'ja', 'en-US', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                """)

                page = await context.new_page()
                await page.set_extra_http_headers(
                    {
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;q=0.9,"
                            "image/avif,image/webp,image/apng,*/*;q=0.8,"
                            "application/signed-exchange;v=b3;q=0.7"
                        ),
                        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                    }
                )

                logging.info(
                    "MizuhoBypass: Navigating to top page first to establish cookies..."
                )
                await page.goto(
                    "https://www.mizuho-re.co.jp/",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                await page.wait_for_timeout(800)
                await page.mouse.move(200, 200)
                await page.wait_for_timeout(200)

                logging.info("MizuhoBypass: Navigating to target list page...")
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=20000
                )
                await page.wait_for_timeout(1500)

                logging.info(
                    "MizuhoBypass: Executing fake mouse movement and scroll..."
                )
                await page.mouse.move(100, 100)
                await page.wait_for_timeout(200)
                await page.mouse.move(300, 400)
                await page.wait_for_timeout(200)
                await page.evaluate("window.scrollTo(0, 500)")
                await page.wait_for_timeout(400)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(400)

                links = await _extract_links_from_page(page, response)
                if not links:
                    logging.warning(
                        "MizuhoBypass: 0 links after first load; reloading in-session..."
                    )
                    await page.wait_for_timeout(3000)
                    await page.goto(
                        "https://www.mizuho-re.co.jp/",
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                    await page.wait_for_timeout(1500)
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=20000
                    )
                    await page.wait_for_timeout(2000)
                    await page.evaluate("window.scrollTo(0, 600)")
                    await page.wait_for_timeout(800)
                    links = await _extract_links_from_page(page, response)
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception as close_error:
                        logging.debug(
                            "MizuhoBypass: Failed to close context: %s",
                            close_error,
                            exc_info=True,
                        )
                if browser:
                    try:
                        await browser.close()
                    except Exception as close_error:
                        logging.debug(
                            "MizuhoBypass: Failed to close browser: %s",
                            close_error,
                            exc_info=True,
                        )
    except Exception as e:
        logging.error(f"MizuhoBypass: Error during Playwright operation: {e}")

    return links


def interpret_mizuho_detail_fetch(url: str, status, title, html_text: str) -> bytes:
    """Playwright詳細取得結果を bytes / 終了 / エラーへ正規化する（単体テスト用に分離）。"""
    logging.info(f"MizuhoBypass: Detail loaded. Title={title!r} Status={status}")
    if status == 403 or "403" in (title or ""):
        raise RuntimeError(f"MizuhoBypass: WAF blocked detail ({status}): {url}")
    if status in (404, 410):
        logging.warning(f"MizuhoBypass: Listing ended HTTP {status} for {url}")
        return b""
    if status and status >= 400:
        raise RuntimeError(f"MizuhoBypass: Detail HTTP {status} for {url}")
    return (html_text or "").encode("utf-8", errors="replace")


async def get_mizuho_page_html(url: str) -> bytes:
    """WAF回避用: Playwrightで詳細ページHTMLを取得する（403/404偽装時のフォールバック）。"""
    logging.info(f"MizuhoBypass: Fetching detail HTML via Playwright: {url}")
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        "--headless=new",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                    viewport={"width": 1280, "height": 800},
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                page = await context.new_page()
                await page.goto(
                    "https://www.mizuho-re.co.jp/",
                    wait_until="networkidle",
                    timeout=20000,
                )
                await page.wait_for_timeout(1000)
                response = await page.goto(
                    url, wait_until="networkidle", timeout=30000
                )
                await page.wait_for_timeout(1500)
                status = response.status if response else None
                title = await page.title()
                content = await page.content()
                return interpret_mizuho_detail_fetch(url, status, title, content)
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception as close_error:
                        logging.debug(
                            "MizuhoBypass: Failed to close context: %s",
                            close_error,
                            exc_info=True,
                        )
                if browser:
                    try:
                        await browser.close()
                    except Exception as close_error:
                        logging.debug(
                            "MizuhoBypass: Failed to close browser: %s",
                            close_error,
                            exc_info=True,
                        )
    except RuntimeError:
        raise
    except Exception as e:
        logging.exception("MizuhoBypass: Detail HTML fetch failed: %s", e)
        raise RuntimeError(f"MizuhoBypass: Playwright failed for {url}: {e}") from e
    return b""


# 投資用パーサーとの後方互換性エイリアス
get_mizuho_investment_links = get_mizuho_links
