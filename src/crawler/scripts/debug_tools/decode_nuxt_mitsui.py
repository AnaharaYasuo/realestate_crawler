# -*- coding: utf-8 -*-
"""
Nuxt3 Devalue 形式の salePropertyData を正確にデコードして実データを表示する
"""
import urllib.request
import json
from bs4 import BeautifulSoup

url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F7BBRA06"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req).read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')

# JSON配列としてロードを試みる
script_content = None
for s_tag in soup.find_all('script'):
    s = s_tag.string or s_tag.get_text() or ""
    if 'salePropertyData' in s and s.strip().startswith('['):
        script_content = s.strip()
        break

if script_content:
    data_pool = json.loads(script_content)
    print(f"Data pool size: {len(data_pool)}")

    def resolve(idx, depth=0):
        if depth > 5:
            return "..."
        if isinstance(idx, int) and 0 <= idx < len(data_pool):
            val = data_pool[idx]
            if isinstance(val, dict):
                return {k: resolve(v, depth+1) for k, v in val.items()}
            elif isinstance(val, list):
                # 特殊マーカー（ShallowReactive等）
                if len(val) >= 2 and isinstance(val[0], str):
                    return resolve(val[1], depth+1)
                return [resolve(x, depth+1) for x in val]
            return val
        return idx

    # salePropertyData を探す
    for i, item in enumerate(data_pool):
        if isinstance(item, dict) and 'salePropertyData' in item:
            sp_idx = item['salePropertyData']
            sp_obj = resolve(sp_idx)
            print("=== DECODED salePropertyData ===")
            for k, v in sp_obj.items():
                if isinstance(v, (dict, list)):
                    v_str = json.dumps(v, ensure_ascii=False)
                    if len(v_str) > 120:
                        v_str = v_str[:120] + "..."
                    print(f"  {k}: {v_str}")
                else:
                    print(f"  {k}: {v}")
            break
else:
    print("Could not find array script")
