# -*- coding: utf-8 -*-
import asyncio
import logging
from playwright.async_api import async_playwright

async def get_mizuho_investment_links(url: str) -> list:
    """
    Playwrightを使ってWAF (403) を回避し、みずほ不動産販売の投資用一覧ページから詳細リンクを抽出する。
    """
    links = []
    logging.info(f"MizuhoBypass: Initializing Playwright bypass for URL: {url}")
    
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            # ブラウザの起動 (ヘッドレス)
            # 新しいヘッドレスモードハック (--headless=new + headless=False) を使用して検出を回避
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--headless=new',
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # 偽装したユーザーコンテキストの生成
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1280, "height": 800}
            )
            
            # webdriverやブラウザ特有プロパティの検出を回避するStealthスクリプトを実行
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
            
            # ブラウザと完全に一致するヘッダーを設定
            await page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            })
            
            # WAF突破のため、最初にトップページにアクセスしてCookieとセッションを構築する
            logging.info("MizuhoBypass: Navigating to top page first to establish cookies...")
            await page.goto("https://www.mizuho-re.co.jp/", wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(2000)
            await page.mouse.move(200, 200)
            await page.wait_for_timeout(500)
            
            # その後、対象の一覧ページへ遷移
            logging.info("MizuhoBypass: Navigating to target list page...")
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # WAFでの読み込み時間を考慮して少し待つ
            await page.wait_for_timeout(3000)
            
            # マウス操作・スクロールを偽装
            logging.info("MizuhoBypass: Executing fake mouse movement and scroll...")
            await page.mouse.move(100, 100)
            await page.wait_for_timeout(500)
            await page.mouse.move(300, 400)
            await page.wait_for_timeout(500)
            await page.evaluate("window.scrollTo(0, 500)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1000)
            
            # タイトルの確認
            title = await page.title()
            logging.info(f"MizuhoBypass: Page loaded. Title: {title}, Status: {response.status if response else 'None'}")
            
            if "403" in title or (response and response.status == 403):
                logging.error("MizuhoBypass: Got blocked with 403!")
            else:
                # リンクの抽出
                hrefs = await page.evaluate("""() => {
                    const links = [];
                    document.querySelectorAll('a').forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && href.includes('/property/')) {
                            links.push(href);
                        }
                    });
                    return links;
                }""")
                
                # 絶対パスへの正規化
                base_url = "https://www.mizuho-re.co.jp"
                for href in hrefs:
                    if href.startswith('/'):
                        full_url = base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        continue
                        
                    # 重複削除
                    if full_url not in links:
                        links.append(full_url)
                        
                logging.info(f"MizuhoBypass: Successfully extracted {len(links)} detailed links via Playwright.")
                
    except Exception as e:
        logging.error(f"MizuhoBypass: Error during Playwright operation: {e}")
    finally:
        if context:
            try:
                await context.close()
            except Exception as e:
                logging.error(f"MizuhoBypass: Error closing context: {e}")
        if browser:
            try:
                await browser.close()
            except Exception as e:
                logging.error(f"MizuhoBypass: Error closing browser: {e}")
            
    return links
