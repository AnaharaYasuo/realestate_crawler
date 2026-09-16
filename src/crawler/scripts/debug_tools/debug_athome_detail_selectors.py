# -*- coding: utf-8 -*-
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def inspect_athome_detail():
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
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        html = await page.content()
        await browser.close()
        
        soup = BeautifulSoup(html, "html.parser")
        print("H1 tags:", [h.get_text().strip() for h in soup.find_all("h1")])
        print("H2 tags:", [h.get_text().strip() for h in soup.find_all("h2")][:5])
        print("Title tag:", soup.title.get_text() if soup.title else "None")
        print("#detailTitleArea:", soup.select_one("#detailTitleArea"))
        print(".bukken-name:", soup.select_one(".bukken-name"))
        print("Header title elements:", [el.get_text().strip() for el in soup.select("h1, h2, .title, .name") if el.get_text().strip()][:10])

if __name__ == "__main__":
    asyncio.run(inspect_athome_detail())
