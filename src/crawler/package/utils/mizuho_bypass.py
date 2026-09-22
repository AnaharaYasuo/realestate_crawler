# -*- coding: utf-8 -*-
import logging
from playwright.async_api import async_playwright

async def _extract_links_from_page(page, response) -> list:
    title = await page.title()
    logging.info(f"MizuhoBypass: Page loaded. Title: {title}, Status: {response.status if response else 'None'}")
    
    if "403" in title or (response and response.status == 403):
        logging.error("MizuhoBypass: Got blocked with 403!")
        return []

    hrefs = await page.evaluate("""() => {
        const links = [];
        document.querySelectorAll('a').forEach(a => {
            const href = a.getAttribute('href');
            if (href && (href.includes('/property/') || href.includes('/buyers/detail/') || href.includes('/investors/detail/'))) {
                links.push(href);
            }
        });
        return links;
    }""")
    
    base_url = "https://www.mizuho-re.co.jp"
    links = []
    for href in hrefs:
        if href.startswith('/'):
            full_url = base_url + href
        elif href.startswith('http'):
            full_url = href
        else:
            continue
        if full_url not in links:
            links.append(full_url)
            
    logging.info(f"MizuhoBypass: Successfully extracted {len(links)} detailed links via Playwright.")
    return links


async def get_mizuho_links(url: str) -> list:
    """Playwrightを使ってWAF (403) を回避し、みずほ不動産販売の一覧ページから詳細リンクを抽出する。"""
    links = []
    logging.info(f"MizuhoBypass: Initializing Playwright bypass for URL: {url}")
    
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        '--headless=new',
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                    viewport={"width": 1280, "height": 800}
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
                await page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1"
                })
                
                logging.info("MizuhoBypass: Navigating to top page first to establish cookies...")
                await page.goto("https://www.mizuho-re.co.jp/", wait_until="networkidle", timeout=20000)
                await page.wait_for_timeout(2000)
                await page.mouse.move(200, 200)
                await page.wait_for_timeout(500)
                
                logging.info("MizuhoBypass: Navigating to target list page...")
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                
                logging.info("MizuhoBypass: Executing fake mouse movement and scroll...")
                await page.mouse.move(100, 100)
                await page.wait_for_timeout(500)
                await page.mouse.move(300, 400)
                await page.wait_for_timeout(500)
                await page.evaluate("window.scrollTo(0, 500)")
                await page.wait_for_timeout(1000)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1000)
                
                links = await _extract_links_from_page(page, response)
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception as close_error:
                        logging.debug("MizuhoBypass: Failed to close context: %s", close_error, exc_info=True)
                if browser:
                    try:
                        await browser.close()
                    except Exception as close_error:
                        logging.debug("MizuhoBypass: Failed to close browser: %s", close_error, exc_info=True)
    except Exception as e:
        logging.error(f"MizuhoBypass: Error during Playwright operation: {e}")

    return links


def interpret_mizuho_detail_fetch(url: str, status, title, html_text: str) -> bytes:
    """Playwright詳細取得結果を bytes / 終了 / エラーへ正規化する（単体テスト用に分離）。"""
    logging.info(f"MizuhoBypass: Detail loaded. Title={title!r} Status={status}")
    if status in (404, 410):
        logging.warning(f"MizuhoBypass: Listing ended HTTP {status} for {url}")
        return b""
    if status == 403 or "403" in (title or ""):
        raise RuntimeError(f"MizuhoBypass: WAF blocked detail ({status}): {url}")
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
                        '--headless=new',
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
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
                await page.goto("https://www.mizuho-re.co.jp/", wait_until="networkidle", timeout=20000)
                await page.wait_for_timeout(1500)
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                status = response.status if response else None
                title = await page.title()
                content = await page.content()
                return interpret_mizuho_detail_fetch(url, status, title, content)
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception as close_error:
                        logging.debug("MizuhoBypass: Failed to close context: %s", close_error, exc_info=True)
                if browser:
                    try:
                        await browser.close()
                    except Exception as close_error:
                        logging.debug("MizuhoBypass: Failed to close browser: %s", close_error, exc_info=True)
    except RuntimeError:
        raise
    except Exception as e:
        logging.exception("MizuhoBypass: Detail HTML fetch failed: %s", e)
        raise RuntimeError(f"MizuhoBypass: Playwright failed for {url}: {e}") from e
    return b""


# 投資用パーサーとの後方互換性エイリアス
get_mizuho_investment_links = get_mizuho_links
