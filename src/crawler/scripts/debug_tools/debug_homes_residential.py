# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_homes_residential():
    print("=== Testing Homes Residential (www.homes.co.jp) ===")
    urls = [
        "https://www.homes.co.jp/mansion/chuko/tokyo/list/",
        "https://www.homes.co.jp/mansion/chuko/tokyo/chiyoda-city/list/",
        "https://www.homes.co.jp/kodate/chuko/tokyo/list/",
        "https://www.homes.co.jp/tochi/tokyo/list/"
    ]
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    print(f"\nURL: {url} | Status: {resp.status}")
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    all_hrefs = [a.get("href") for a in soup.find_all("a", href=True)]
                    print(f"Total hrefs: {len(all_hrefs)}")
                    
                    detail_hrefs = [h for h in all_hrefs if "/bukkendetail/" in h or "/detail/" in h or "b-id" in h or re.search(r'/chuko/b-\d+/', h)]
                    print(f"Detail-like hrefs found: {len(detail_hrefs)}. Samples: {detail_hrefs[:5]}")
                    
                    # 別のクラス名・属性のパターン
                    item_blocks = soup.select(".mod-mergeOfferModule") or soup.select(".cassetteList") or soup.select("article")
                    print(f"Item block elements found: {len(item_blocks)}")
            except Exception as e:
                print(f"Error for {url}: {e}")

if __name__ == "__main__":
    asyncio.run(test_homes_residential())
