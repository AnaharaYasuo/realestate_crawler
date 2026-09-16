# -*- coding: utf-8 -*-
import urllib.request

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def check_url(url):
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req)
        html = res.read().decode('utf-8', 'ignore')
        print(f"SUCCESS {res.status}: {url} (Length: {len(html)})")
        return html
    except Exception as e:
        print(f"FAILED: {url} -> {e}")
        return None

print("Checking Mitsui URLs...")
check_url("https://www.rehouse.co.jp/buy/")
check_url("https://www.rehouse.co.jp/buy/mansion/")
check_url("https://www.rehouse.co.jp/buy/mansion/tokyo/")
check_url("https://www.rehouse.co.jp/buy/mansion/area/13/")
check_url("https://www.rehouse.co.jp/buy/mansion/pref/13/")

html = check_url("https://www.rehouse.co.jp/buy/mansion/")
if html:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text().strip()
        if '/buy/mansion' in href or '東京' in text or '神奈川' in text:
            print(f"  [{text}] -> {href}")

print("\nChecking Tokyu URLs...")
check_url("https://www.livable.co.jp/mansion/")
check_url("https://www.livable.co.jp/mansion/tokyo/")
check_url("https://www.livable.co.jp/mansion/kanto/")
check_url("https://www.livable.co.jp/buy/mansion/")
