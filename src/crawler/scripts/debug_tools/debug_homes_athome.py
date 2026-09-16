# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_homes():
    print("=== Testing Homes ===")
    url = "https://toushi.homes.co.jp/bukkensearch/tbg[]=2/"
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                print(f"Homes Start URL Status: {resp.status}, Final URL: {resp.url}")
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                
                canonical = soup.find("link", rel="canonical")
                print(f"Homes Canonical: {canonical.get('href') if canonical else 'None'}")
                
                # Check detail links
                links = []
                for a in soup.select("a[href*='/bukkendetail/']"):
                    href = a.get("href")
                    links.append(href)
                print(f"Found {len(links)} links with '/bukkendetail/'. Samples: {links[:5]}")
                
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                print(f"Homes total links: {len(all_links)}")
                bukkend_links = [l for l in all_links if "detail" in l or "bukken" in l]
                print(f"Found {len(bukkend_links)} links matching 'detail' or 'bukken'. Samples: {bukkend_links[:10]}")
    except Exception as e:
        print(f"Homes Error: {e}")

async def test_athome():
    print("\n=== Testing Athome ===")
    url = "https://www.athome.co.jp/mansion/"
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                print(f"Athome Start URL Status: {resp.status}, Final URL: {resp.url}")
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                print(f"Athome Total links: {len(all_links)}")
                mansion_links = [l for l in all_links if "/mansion/" in l or "/toushi/" in l]
                print(f"Found {len(mansion_links)} links matching '/mansion/' or '/toushi/'. Samples: {mansion_links[:10]}")
                
                regex_matches = [l for l in all_links if re.match(r'^/(mansion|kodate|toushi|tochi)/\d+/?$', urllib.parse.urlparse(l).path)]
                print(f"Regex matches count: {len(regex_matches)}")
    except Exception as e:
        print(f"Athome Error: {e}")

async def main():
    await test_homes()
    await test_athome()

if __name__ == "__main__":
    asyncio.run(main())
