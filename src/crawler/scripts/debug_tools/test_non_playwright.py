# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_aiohttp_sites():
    test_urls = {
        "Daikyo": "https://www.daikyo-anabuki.co.jp/buy/mansion/",
        "Keikyu": "https://www.keikyu-sumai.com/buy/",
        "Keisei": "https://www.keisei-fudosan.co.jp/",
        "Seibu": "https://www.seibu-realestate.co.jp/",
        "Sotetsu": "https://www.sotetsu-re.co.jp/",
        "Rearie": "https://rearie.jp/",
        "Keio": "https://www.keio-fudosan.co.jp/",
        "Heim": "https://www.sekisuiheim-fudosan.co.jp/"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for name, url in test_urls.items():
            try:
                async with session.get(url, timeout=10) as resp:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    print(f"[{name}] Status: {resp.status}, HTML len: {len(html)}, Title: {soup.title.string.strip() if soup.title else 'No Title'}")
            except Exception as e:
                print(f"[{name}] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_aiohttp_sites())
