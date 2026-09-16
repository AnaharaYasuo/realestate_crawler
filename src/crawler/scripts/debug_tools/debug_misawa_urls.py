# -*- coding: utf-8 -*-
import urllib.request
import ssl

ctx = ssl._create_unverified_context()
ctx.set_ciphers('DEFAULT@SECLEVEL=1')
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def check_url(url):
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        html = res.read().decode('utf-8', 'ignore')
        print(f"SUCCESS {res.status}: {url} (Length: {len(html)})")
        return html
    except Exception as e:
        print(f"FAILED: {url} -> {e}")
        return None

print("Testing Misawa search URLs...")
check_url("https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=9")
check_url("https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=10")
check_url("https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=11")
