# -*- coding: utf-8 -*-
"""
実サイト接続＆最新物件ページ構造・属性徹底調査スクリプト
"""
import asyncio
import aiohttp
import re
import json
import os
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
}

REHOUSE_BASE_URL = "https://www.rehouse.co.jp"

TARGET_URLS = [
    # 三井のリハウス (マンション、戸建て、土地)
    ("mitsui_mansion_list", f"{REHOUSE_BASE_URL}/buy/mansion/prefecture/13/city/13101/", r"/buy/mansion/bkdetail/[A-Za-z0-9]+", REHOUSE_BASE_URL),
    ("mitsui_kodate_list", f"{REHOUSE_BASE_URL}/buy/kodate/prefecture/13/city/13101/", r"/buy/kodate/bkdetail/[A-Za-z0-9]+", REHOUSE_BASE_URL),
    ("mitsui_tochi_list", f"{REHOUSE_BASE_URL}/buy/tochi/prefecture/13/city/13101/", r"/buy/tochi/bkdetail/[A-Za-z0-9]+", REHOUSE_BASE_URL),
    # 東急リバブル (マンション、戸建て)
    ("tokyu_mansion_list", "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13101/", r"/mansion/C[A-Za-z0-9]+", "https://www.livable.co.jp"),
    ("tokyu_kodate_list", "https://www.livable.co.jp/kounyu/kodate/tokyo/a13101/", r"/kodate/C[A-Za-z0-9]+", "https://www.livable.co.jp"),
    # 野村の仲介＋ (nomu.com)
    ("nomu_mansion_list", "https://www.nomu.com/mansion/tokyo/chiyoda-ku/", r"/mansion/id/[A-Za-z0-9]+", "https://www.nomu.com"),
]

async def fetch_html(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
            else:
                print(f"Failed {url}: status {resp.status}")
                return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_all_page_attributes(html_text, site_key, url):
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # 1. 全ての table から th/td ペアを抽出
    table_data = {}
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            ths = [th.get_text(strip=True) for th in row.find_all(['th'])]
            tds = [td.get_text(strip=True) for td in row.find_all(['td'])]
            if ths and tds:
                # 1対1 または 複数ペア
                if len(ths) == len(tds):
                    for h, d in zip(ths, tds):
                        if h:
                            table_data[h] = d
                elif len(ths) == 1 and len(tds) >= 1:
                    table_data[ths[0]] = " | ".join(tds)
                else:
                    table_data[" / ".join(ths)] = " / ".join(tds)
    
    # 2. dl / dt / dd ペアの抽出
    dl_data = {}
    for dl in soup.find_all('dl'):
        dts = [dt.get_text(strip=True) for dt in dl.find_all('dt')]
        dds = [dd.get_text(strip=True) for dd in dl.find_all('dd')]
        if len(dts) == len(dds):
            for t, d in zip(dts, dds):
                if t:
                    dl_data[t] = d
                    
    # 3. 特徴・設備タグ（リスト、チェック項目）
    features = []
    for el in soup.find_all(class_=re.compile(r'feature|equipment|icon|tag|point|spec|merit', re.I)):
        text = el.get_text(strip=True)
        if text and len(text) < 100 and text not in features:
            # 除外：短すぎるものや数字のみ
            if len(text) > 1 and not text.isdigit():
                features.append(text)
                
    # 4. アピールテキスト・キャッチコピー・おすすめコメント
    appeal_texts = []
    for el in soup.find_all(class_=re.compile(r'catch|comment|recommend|point|description|pr', re.I)):
        text = el.get_text(strip=True)
        if text and len(text) > 20 and text not in appeal_texts:
            appeal_texts.append(text[:300]) # 先頭300文字
            
    # 5. Nuxt / Next SSR JSON などの埋め込みスクリプト調査
    json_scripts = []
    for s in soup.find_all('script'):
        if s.string and ('window.__NUXT__' in s.string or 'application/json' in s.get('type', '')):
            json_scripts.append(s.string[:500])

    return {
        "site_key": site_key,
        "url": url,
        "title": soup.title.string if soup.title else "",
        "table_data": table_data,
        "dl_data": dl_data,
        "features_sample": features[:30],
        "appeal_texts": appeal_texts[:5],
        "has_ssr_json": len(json_scripts) > 0,
    }

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        results = []
        for site_key, list_url, detail_regex, base_url in TARGET_URLS:
            print(f"Fetching list: {list_url}")
            list_html = await fetch_html(session, list_url)
            if not list_html:
                continue
            
            # 詳細URLを抽出
            matches = re.findall(detail_regex, list_html)
            if not matches:
                # 汎用的なリンク探索
                soup = BeautifulSoup(list_html, 'html.parser')
                for a in soup.find_all('a', href=True):
                    if re.search(detail_regex, a['href']):
                        matches.append(a['href'])
            
            unique_details = []
            for m in matches:
                if m.startswith('http'):
                    u = m
                elif m.startswith('/'):
                    u = base_url + m
                else:
                    u = base_url + '/' + m
                if u not in unique_details:
                    unique_details.append(u)
            
            print(f"[{site_key}] Found {len(unique_details)} detail URLs. Sampling top 1...")
            if unique_details:
                detail_url = unique_details[0]
                print(f"Fetching detail: {detail_url}")
                detail_html = await fetch_html(session, detail_url)
                if detail_html:
                    attr_data = extract_all_page_attributes(detail_html, site_key, detail_url)
                    results.append(attr_data)
                await asyncio.sleep(1) #礼儀正しい間隔
                
        return results

if __name__ == '__main__':
    survey_results = asyncio.run(main())
    output_path = "src/crawler/package/ml/logs/live_site_attributes_survey.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(survey_results, f, ensure_ascii=False, indent=2)
    print(f"Survey completed. Saved to {output_path}")
