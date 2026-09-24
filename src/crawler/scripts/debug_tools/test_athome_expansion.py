# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_athome_expansion():
    urls = [
        "https://www.athome.co.jp/mansion/chuko/tokyo/city/",
        "https://www.athome.co.jp/kodate/chuko/tokyo/city/",
        "https://www.athome.co.jp/tochi/tokyo/city/",
        "https://www.athome.co.jp/toushi/tokyo/city/"
    ]
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            async with session.get(url) as resp:
                print(f"\nURL: {url} | Status: {resp.status}")
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                
                links = set()
                for a in soup.find_all("a", href=True):
                    href = a.get("href")
                    path = urllib.parse.urlparse(href).path
                    if "/list/" in path or re.search(r'/(mansion|kodate|tochi|toushi)/\d{5,}/?', path):
                        links.add(href)
                print(f"Extracted list/detail links count: {len(links)}. Samples: {list(links)[:5]}")

if __name__ == "__main__":
    asyncio.run(test_athome_expansion())
