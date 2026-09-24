# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_athome_city_list():
    print("=== Testing Athome Specific City List Page ===")
    url = "https://www.athome.co.jp/mansion/chuko/tokyo/chiyoda-city/list/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(f"Athome City List Status: {resp.status}")
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            
            all_links = [a.get("href") for a in soup.find_all("a", href=True)]
            detail_links = set()
            for href in all_links:
                path = urllib.parse.urlparse(href).path
                if re.match(r'^/(mansion|kodate|toushi|tochi)/\d{5,}/?$', path):
                    detail_links.add(href)
            print(f"Athome detail links found: {len(detail_links)}. Samples: {list(detail_links)[:5]}")

async def test_homes_city_list():
    print("\n=== Testing Homes Specific City List Page ===")
    url = "https://www.homes.co.jp/mansion/chuko/tokyo/chiyoda-city/list/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(f"Homes City List Status: {resp.status}")
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            
            all_links = [a.get("href") for a in soup.find_all("a", href=True)]
            detail_links = set()
            for href in all_links:
                if "/bukkendetail/" in href or "bukkendetail" in href:
                    detail_links.add(href)
            print(f"Homes detail links found: {len(detail_links)}. Samples: {list(detail_links)[:5]}")

async def test_homes_toushi_list():
    print("\n=== Testing Homes Toushi List Page ===")
    url = "https://toushi.homes.co.jp/bukkensearch/tokyo/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            print(f"Homes Toushi Status: {resp.status}")
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            
            all_links = [a.get("href") for a in soup.find_all("a", href=True)]
            detail_links = set()
            for href in all_links:
                if "bukkendetail" in href or "/bukkendetail/" in href:
                    detail_links.add(href)
            print(f"Homes Toushi detail links found: {len(detail_links)}. Samples: {list(detail_links)[:5]}")

async def main():
    await test_athome_city_list()
    await test_homes_city_list()
    await test_homes_toushi_list()

if __name__ == "__main__":
    asyncio.run(main())
