# -*- coding: utf-8 -*-
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import urllib.parse
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

async def test_athome_list():
    print("=== Testing Athome Tokyo List Page ===")
    # 東京都の中古マンション一覧
    url = "https://www.athome.co.jp/mansion/chuko/tokyo/city/"
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                print(f"Athome List URL Status: {resp.status}, Final URL: {resp.url}")
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                print(f"Athome Total links on city page: {len(all_links)}")
                
                # 詳細物件URLのチェック (/mansion/xxxxxxx/)
                detail_links = []
                for l in all_links:
                    path = urllib.parse.urlparse(l).path
                    if re.search(r'/(mansion|kodate|tochi|toushi)/[0-9]{5,}/?', path):
                        detail_links.append(l)
                print(f"Athome detail links found: {len(detail_links)}. Samples: {detail_links[:5]}")
                
                # 市区町村一覧ページのリンクチェック
                city_links = [l for l in all_links if "/tokyo/" in l and ("-city" in l or "list" in l or "/city/" in l)]
                print(f"Athome city list links: {len(city_links)}. Samples: {city_links[:5]}")
    except Exception as e:
        print(f"Athome List Error: {e}")

async def test_homes_list():
    print("\n=== Testing Homes Tokyo List Page ===")
    # Homes 中古マンション 一覧ページ
    url = "https://www.homes.co.jp/mansion/chuko/tokyo/city/"
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                print(f"Homes List URL Status: {resp.status}, Final URL: {resp.url}")
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                
                all_links = [a.get("href") for a in soup.find_all("a", href=True)]
                print(f"Homes Total links on city page: {len(all_links)}")
                
                detail_links = [l for l in all_links if "/bukkendetail/" in l or "bukkendetail" in l]
                print(f"Homes detail links found: {len(detail_links)}. Samples: {detail_links[:5]}")
                
                list_links = [l for l in all_links if "/mansion/chuko/" in l]
                print(f"Homes list links: {len(list_links)}. Samples: {list_links[:5]}")
    except Exception as e:
        print(f"Homes List Error: {e}")

async def main():
    await test_athome_list()
    await test_homes_list()

if __name__ == "__main__":
    asyncio.run(main())
