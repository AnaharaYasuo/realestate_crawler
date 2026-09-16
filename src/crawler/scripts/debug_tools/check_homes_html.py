# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
}

async def check_homes_html():
    url = "https://www.homes.co.jp/mansion/chuko/tokyo/chiyoda-city/list/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(f"Status: {resp.status}")
            html = await resp.text()
            print(f"HTML Length: {len(html)}")
            soup = BeautifulSoup(html, "html.parser")
            print(f"Title: {soup.title.string if soup.title else 'No Title'}")
            print(f"HTML snippet:\n{html[:1000]}")

if __name__ == "__main__":
    asyncio.run(check_homes_html())
