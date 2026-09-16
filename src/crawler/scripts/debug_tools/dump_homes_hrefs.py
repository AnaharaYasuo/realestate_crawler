# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def dump_homes_hrefs():
    url = "https://www.homes.co.jp/mansion/chuko/tokyo/chiyoda-city/list/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            
            all_hrefs = set([a.get("href") for a in soup.find_all("a", href=True)])
            print(f"Unique hrefs count: {len(all_hrefs)}")
            for h in sorted(list(all_hrefs))[:30]:
                print(f"  {h}")

if __name__ == "__main__":
    asyncio.run(dump_homes_hrefs())
