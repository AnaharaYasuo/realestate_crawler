# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.api.registry import ApiRegistry

ZERO_MODELS = [
    ("afr", "mansion"),
    ("athome", "invest_apartment"),
    ("daikyo", "kodate"),
    ("daikyo", "tochi"),
    ("daiwa", "kodate"),
    ("daiwa", "tochi"),
    ("heim", "mansion"),
    ("keikyu", "kodate"),
    ("keikyu", "tochi"),
    ("keisei", "kodate"),
    ("keisei", "mansion"),
    ("keisei", "tochi"),
    ("mizuho", "kodate"),
    ("mizuho", "tochi"),
    ("odakyu", "investment"),
    ("odakyu", "kodate"),
    ("odakyu", "tochi"),
    ("rearie", "kodate"),
    ("rearie", "mansion"),
    ("rearie", "tochi"),
    ("sekisui", "kodate"),
    ("sekisui", "mansion"),
]

async def diagnose_zero_models():
    print("=== ZERO COUNT MODELS DIAGNOSIS ===")
    async with aiohttp.ClientSession():
        for company, ptype in ZERO_MODELS:
            start_api_path = f"/api/{company}/{ptype}/start"
            api_cls = ApiRegistry.get(start_api_path)
            if not api_cls:
                print(f"❌ [NO API REGISTRY] {company} - {ptype} ({start_api_path})")
                continue
                
            proc = api_cls()
            print(f"\n🔍 Diagnosing {company} - {ptype}...")
            # ルートURL等の取得テスト
            try:
                print(f"   API Class: {api_cls.__name__}, Parser: {proc.parser.__class__.__name__}")
            except Exception as e:
                print(f"   Error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_zero_models())
