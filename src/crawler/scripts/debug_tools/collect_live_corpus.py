# -*- coding: utf-8 -*-
"""
多数の実在物件（マンション・戸建て・土地・投資）の詳細データ一括収集スクリプト
"""
import asyncio
import aiohttp
import re
import json
import os
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
}

TARGET_SOURCES = [
    # 三井のリハウス (各カテゴリ 5〜6件)
    {"site": "mitsui", "type": "mansion", "list": "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/", "pattern": r"/buy/mansion/bkdetail/[A-Za-z0-9]+", "base": "https://www.rehouse.co.jp", "limit": 6},
    {"site": "mitsui", "type": "kodate", "list": "https://www.rehouse.co.jp/buy/kodate/prefecture/13/city/13101/", "pattern": r"/buy/kodate/bkdetail/[A-Za-z0-9]+", "base": "https://www.rehouse.co.jp", "limit": 6},
    {"site": "mitsui", "type": "tochi", "list": "https://www.rehouse.co.jp/buy/tochi/prefecture/13/city/13101/", "pattern": r"/buy/tochi/bkdetail/[A-Za-z0-9]+", "base": "https://www.rehouse.co.jp", "limit": 6},
    {"site": "mitsui", "type": "mansion", "list": "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13103/", "pattern": r"/buy/mansion/bkdetail/[A-Za-z0-9]+", "base": "https://www.rehouse.co.jp", "limit": 6}, # 港区
    # 東急リバブル
    {"site": "tokyu", "type": "mansion", "list": "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13101/", "pattern": r"/mansion/C[A-Za-z0-9]+", "base": "https://www.livable.co.jp", "limit": 6},
    {"site": "tokyu", "type": "kodate", "list": "https://www.livable.co.jp/kounyu/kodate/tokyo/a13101/", "pattern": r"/kodate/C[A-Za-z0-9]+", "base": "https://www.livable.co.jp", "limit": 4},
    {"site": "tokyu", "type": "tochi", "list": "https://www.livable.co.jp/kounyu/tochi/tokyo/a13103/", "pattern": r"/tochi/C[A-Za-z0-9]+", "base": "https://www.livable.co.jp", "limit": 4},
    # 野村の仲介＋
    {"site": "nomu", "type": "mansion", "list": "https://www.nomu.com/mansion/tokyo/chiyoda-ku/", "pattern": r"/mansion/id/[A-Za-z0-9]+", "base": "https://www.nomu.com", "limit": 6},
    {"site": "nomu", "type": "kodate", "list": "https://www.nomu.com/house/tokyo/chiyoda-ku/", "pattern": r"/house/id/[A-Za-z0-9]+", "base": "https://www.nomu.com", "limit": 4},
    {"site": "nomu", "type": "invest", "list": "https://www.nomu.com/pro/search/tokyo/", "pattern": r"/pro/id/[A-Za-z0-9]+", "base": "https://www.nomu.com", "limit": 5},
]

async def fetch(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"Fetch error {url}: {e}")
    return None

def extract_property_summary(html, site, prop_type, url):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.string.strip() if soup.title else ""
    
    # テーブル・リストデータ
    specs = {}
    for tr in soup.find_all('tr'):
        ths = [th.get_text(strip=True) for th in tr.find_all('th')]
        tds = [td.get_text(strip=True) for td in tr.find_all('td')]
        if ths and tds:
            if len(ths) == len(tds):
                for h, d in zip(ths, tds):
                    if h: specs[h] = d
            elif len(ths) == 1:
                specs[ths[0]] = " | ".join(tds)
                
    for dl in soup.find_all('dl'):
        dts = [dt.get_text(strip=True) for dt in dl.find_all('dt')]
        dds = [dd.get_text(strip=True) for dd in dl.find_all('dd')]
        for h, d in zip(dts, dds):
            if h and d and h not in specs:
                specs[h] = d

    # 特徴タグ
    features = []
    for el in soup.find_all(class_=re.compile(r'feature|point|tag|icon|spec|merit', re.I)):
        t = el.get_text(strip=True)
        if 2 < len(t) < 60 and not t.isdigit() and t not in features:
            features.append(t)

    # アピール文章
    appeals = []
    for el in soup.find_all(class_=re.compile(r'catch|comment|recommend|description|pr|point', re.I)):
        t = el.get_text(strip=True)
        if 20 < len(t) < 400 and t not in appeals:
            appeals.append(t)

    # Nuxt SSR からのリノベ・設備・スコア・共用施設等の生テキスト
    nuxt_info = []
    for s in soup.find_all('script'):
        if s.string and ('salePropertyData' in s.string or '__NUXT__' in s.string):
            # 特徴的な単語を含む文字列リテラルを抽出
            lits = re.findall(r'"([^"]{4,80})"', s.string)
            for lit in lits:
                if any(w in lit for w in ['エレベーター', 'ペット', '角部屋', 'ルーフバルコニー', '専用庭', '宅配ボックス', 'ディスポーザー', '食洗機', '床暖房', '浴室乾燥', '内廊下', '管理', '修繕', '耐震', 'リフォーム', 'リノベーション', '分譲', '施工', '借地', '接道', '公道', '私道', 'スコア', 'CATV']):
                    if lit not in nuxt_info:
                        nuxt_info.append(lit)

    return {
        "url": url,
        "site": site,
        "property_type": prop_type,
        "title": title,
        "specs": specs,
        "features": features[:20],
        "appeals": appeals[:5],
        "nuxt_extracted_snippets": nuxt_info[:20]
    }

async def collect():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        all_properties = []
        for src in TARGET_SOURCES:
            print(f"Collecting list: {src['list']} ({src['site']}_{src['type']})")
            l_html = await fetch(session, src['list'])
            if not l_html:
                continue
            
            raw_urls = re.findall(src['pattern'], l_html)
            urls = []
            for u in raw_urls:
                full = u if u.startswith('http') else (src['base'] + u if u.startswith('/') else src['base'] + '/' + u)
                if full not in urls:
                    urls.append(full)
            
            selected = urls[:src['limit']]
            print(f"  -> Found {len(urls)} URLs. Fetching {len(selected)} details...")
            for u in selected:
                d_html = await fetch(session, u)
                if d_html:
                    prop_info = extract_property_summary(d_html, src['site'], src['type'], u)
                    all_properties.append(prop_info)
                await asyncio.sleep(0.5)

        out_path = "src/crawler/package/ml/logs/corpus_40_live_properties.json"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_properties, f, ensure_ascii=False, indent=2)
        print(f"Successfully collected {len(all_properties)} live properties! Saved to {out_path}")

if __name__ == '__main__':
    asyncio.run(collect())
