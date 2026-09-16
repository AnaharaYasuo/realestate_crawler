# -*- coding: utf-8 -*-
import sys
import os

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        break
    _cur = _parent

from package.api.mitsui import ParseMitsuiMansionStartAsync
from package.api.tokyu import ParseTokyuMansionStartAsync

print("--- Testing Mitsui Mansion Start ---")
res_mitsui = ParseMitsuiMansionStartAsync().main("https://www.rehouse.co.jp/buy/mansion/")
print(f"Mitsui extracted {len(res_mitsui)} area URLs:")
for u in res_mitsui[:5]:
    print("  ", u)

print("--- Testing Mitsui Mansion Start ---")
res_mitsui = ParseMitsuiMansionStartAsync().main("https://www.rehouse.co.jp/buy/mansion/")
print(f"Mitsui extracted {len(res_mitsui)} area URLs:")
for u in res_mitsui[:5]:
    print("  ", u)

print("\n--- Testing Tokyu Mansion Start ---")
res_tokyu = ParseTokyuMansionStartAsync().main("https://www.livable.co.jp/mansion/")
print(f"Tokyu extracted {len(res_tokyu)} area URLs:")
for u in res_tokyu[:5]:
    print("  ", u)
