# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright

async def test_playwright_stealth():
    url = "https://www.athome.co.jp/mansion/6991572422/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certificate-errors',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ja-JP',
            timezone_id='Asia/Tokyo'
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()
        print(f"Navigating to {url}...")
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"Response status: {resp.status if resp else 'None'}")
        
        await page.wait_for_timeout(2000)
        content = await page.content()
        print(f"Content length: {len(content)}")
        
        if "認証にご協力ください" in content or "Click to verify" in content:
            print("❌ Detected Bot Challenge Screen!")
        else:
            print("✅ Successfully bypassed Bot Challenge!")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            print(f"Title: {soup.title.string if soup.title else 'No Title'}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_playwright_stealth())
