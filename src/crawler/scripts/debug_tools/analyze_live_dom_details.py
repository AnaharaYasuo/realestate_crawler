# -*- coding: utf-8 -*-
"""
実サイト詳細ページの網羅的項目ダンプ＆未取得観点分析スクリプト
"""
import urllib.request
import re
import json
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

SAMPLES = [
    ("三井マンション", "https://www.rehouse.co.jp/buy/mansion/bkdetail/F7BBRA06"),
    ("三井戸建て", "https://www.rehouse.co.jp/buy/kodate/bkdetail/FJTAGA3A"),
    ("三井土地", "https://www.rehouse.co.jp/buy/tochi/bkdetail/FEUBEA04"),
    ("東急マンション", "https://www.livable.co.jp/mansion/C13269U95"),
    ("東急戸建て", "https://www.livable.co.jp/kodate/C13269J50"),
    ("野村マンション", "https://www.nomu.com/mansion/id/R5770923"),
]

def analyze_page(name, url):
    print(f"\n{'='*30} {name} {'='*30}")
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(html, 'html.parser')

    # 1. 見出しやタイトル
    title = soup.title.string.strip() if soup.title else ""
    print(f"TITLE: {title}")

    # 2. Nuxt / JSON データ内のプロパティ探索（三井などの場合）
    nuxt_matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in nuxt_matches:
        if 'window.__NUXT__' in s or 'salePropertyData' in s:
            # 文字列リテラルを抽出
            literals = re.findall(r'"([^"]{2,50})"', s)
            # 特徴的な単語（エレベーター、管理、修繕、リフォーム、角部屋、ペット、向き、施工、分譲など）を探索
            keywords = [
                "エレベーター", "ペット", "角部屋", "ルーフバルコニー", "専用庭", "トランクルーム",
                "宅配ボックス", "ディスポーザー", "食洗機", "床暖房", "浴室乾燥", "24時間ゴミ出し",
                "二重床", "二重天井", "免震", "制震", "耐震", "内廊下", "外廊下",
                "日勤", "常駐", "巡回", "全部委託", "自主管理", "修繕積立金", "修繕履歴",
                "長期修繕計画", "瑕疵保険", "新耐震", "旧耐震", "耐震基準適合",
                "分譲", "施工", "設計", "用途地域", "建ぺい率", "容積率",
                "私道", "セットバック", "接道", "公道", "地目", "都市計画",
                "総戸数", "階数", "所在階", "向き", "眺望", "陽当り", "通風",
                "リフォーム", "リノベーション", "現況", "引渡", "告知事項", "借地権", "借地期間"
            ]
            found = set()
            for lit in literals:
                for kw in keywords:
                    if kw in lit:
                        found.add(lit)
            if found:
                print(f"-- NUXT/STATE KEYWORDS FOUND ({len(found)}) --")
                for f_item in sorted(list(found))[:30]:
                    print(f"   * {f_item}")

    # 3. HTML内の全テーブル th/td
    tables = soup.find_all('table')
    if tables:
        print(f"-- TABLE ITEMS ({len(tables)} tables) --")
        for t_idx, t in enumerate(tables):
            for tr in t.find_all('tr'):
                ths = [th.get_text(strip=True) for th in tr.find_all('th')]
                tds = [td.get_text(strip=True) for td in tr.find_all('td')]
                if ths and tds:
                    print(f"   [{' / '.join(ths)}]: {' / '.join(tds)[:70]}")

    # 4. HTML内の dl/dt/dd
    dls = soup.find_all('dl')
    if dls:
        print(f"-- DL ITEMS ({len(dls)} dls) --")
        for dl in dls:
            dts = [dt.get_text(strip=True) for dt in dl.find_all('dt')]
            dds = [dd.get_text(strip=True) for dd in dl.find_all('dd')]
            if dts and dds:
                for dt_val, dd_val in zip(dts, dds):
                    if dt_val and dd_val and len(dd_val) > 0:
                        print(f"   [{dt_val}]: {dd_val[:70]}")

    # 5. セールスポイント・アピールテキスト（箇条書きや文章）
    print("-- HIGHLIGHTS / POINTS / COMMENTS --")
    points = []
    for el in soup.find_all(['li', 'p', 'div'], class_=re.compile(r'point|catch|comment|recommend|feature|appeal|tag', re.I)):
        text = el.get_text(strip=True)
        if 15 < len(text) < 200 and text not in points:
            points.append(text)
    for p in points[:10]:
        print(f"   - {p}")

def main():
    for name, url in SAMPLES:
        analyze_page(name, url)

if __name__ == '__main__':
    main()
