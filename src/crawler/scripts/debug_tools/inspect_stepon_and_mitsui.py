# -*- coding: utf-8 -*-
"""
住友ステップ＆三井Nuxtデータ深掘りスクリプト
"""
import urllib.request
import re
import json
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# 住友ステップの一覧から詳細を取得
def inspect_stepon():
    list_url = "https://www.stepon.co.jp/mansion/tokyo/13101/"
    print(f"Fetching stepon: {list_url}")
    req = urllib.request.Request(list_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        matches = re.findall(r'/mansion/detail/([A-Za-z0-9]+)/', html)
        if matches:
            detail_url = f"https://www.stepon.co.jp/mansion/detail/{matches[0]}/"
            print(f"Stepon detail: {detail_url}")
            req_d = urllib.request.Request(detail_url, headers=HEADERS)
            with urllib.request.urlopen(req_d, timeout=10) as resp_d:
                d_html = resp_d.read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(d_html, 'html.parser')
            print("Stepon Title:", soup.title.string if soup.title else "")
            for tr in soup.find_all('tr'):
                ths = [th.get_text(strip=True) for th in tr.find_all('th')]
                tds = [td.get_text(strip=True) for td in tr.find_all('td')]
                if ths and tds:
                    print(f"  [Stepon Table] {' / '.join(ths)}: {' / '.join(tds)[:60]}")
            # 特徴リスト
            features = [el.get_text(strip=True) for el in soup.find_all(class_=re.compile(r'feature|point|tag|icon|spec', re.I))]
            print("  [Stepon Features sample]:", features[:15])
    except Exception as e:
        print("Stepon error:", e)

# 三井Nuxtスクリプトの詳細解析
def inspect_mitsui_nuxt():
    url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F7BBRA06"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    # scriptタグから、キーと値のペアを探索
    # 例: "floorPlan":"ワンルーム", "renovation"...
    matches = re.findall(r'\"([a-zA-Z0-9_]{3,35})\":(\"[^\"]{1,100}\"|\d+|true|false|null)', html)
    print(f"\n--- MITSUI NUXT KEY-VALUES (Total {len(matches)} pairs) ---")
    interesting_kvs = {}
    for k, v in matches:
        if any(w in k.lower() for w in ['floor', 'room', 'area', 'renov', 'pet', 'park', 'elev', 'balcony', 'direct', 'manage', 'cost', 'fee', 'build', 'sell', 'right', 'land', 'status', 'view', 'equip', 'tag', 'point', 'feature', 'repair']):
            interesting_kvs[k] = v
    for k, v in sorted(interesting_kvs.items()):
        print(f"  {k}: {v}")

def inspect_mitsui_types():
    targets = [
        ("三井戸建て", "https://www.rehouse.co.jp/buy/kodate/bkdetail/FJTAGA3A"),
        ("三井土地", "https://www.rehouse.co.jp/buy/tochi/bkdetail/FEUBEA04"),
    ]
    for name, url in targets:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        matches = re.findall(r'"([a-zA-Z0-9_]{3,35})":("([^"]{1,100})"|\d+|true|false|null)', html)
        print(f"\n=== {name} (Matches: {len(matches)}) ===")
        found = {}
        for item in matches:
            k = item[0]
            v = item[1]
            if any(w in k.lower() for w in ['road', 'land', 'build', 'car', 'park', 'water', 'gas', 'sewer', 'law', 'zone', 'ratio', 'setback', 'slope', 'condition', 'structure', 'area', 'price']):
                found[k] = v
        for k, v in sorted(found.items())[:30]:
            print(f"  {k}: {v}")

if __name__ == '__main__':
    inspect_stepon()
    inspect_mitsui_nuxt()
    inspect_mitsui_types()

