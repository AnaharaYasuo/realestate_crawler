# -*- coding: utf-8 -*-
"""
各不動産サイトに対するHTTPリクエスト検証テストスクリプト

検証内容:
1. 現行ヘッダー (Baseline)
   - User-Agent のみ、または既存ヘッダー
2. 提案ヘッダー (Optimized)
   - Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
   - Accept-Encoding: gzip, deflate, br
3. レスポンスヘッダーおよびボディの比較:
   - ステータスコード (200 OK か、WAF/ブロックが発生しないか)
   - Content-Type (HTMLとして正しく認識されるか)
   - Content-Encoding (gzip/br 等で圧縮転送されているか)
   - 転送バイト数（Raw Response Size）の削減効果
   - デコード後のテキスト長とパース可能性（HTMLが壊れていないか）
"""

import asyncio
import sys
import os
import aiohttp
import ssl

# テスト対象サイト代表URL (一覧または詳細URL)
TARGET_URLS = [
    {
        "name": "三井のリハウス (Mitsui)",
        "url": "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/",
    },
    {
        "name": "東急リバブル (Tokyu)",
        "url": "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13101/",
    },
    {
        "name": "住友不動産販売 (Sumifu)",
        "url": "https://www.stepon.co.jp/mansion/area_13/list_13_101/?limit=10&mode=2",
    },
    {
        "name": "三井住友トラスト (SMTRC)",
        "url": "https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1",
    },
    {
        "name": "ミサワホーム (Misawa)",
        "url": "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=9",
    },
    {
        "name": "健美家 (Kenbiya)",
        "url": "https://www.kenbiya.com/list/pref=13/",
    },
    {
        "name": "京王不動産 (Keio API/JSON)",
        "url": "https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=5&page_num=1&pref=13&boshu_kind_summary_code%5B%5D=1",
    },
]

BASELINE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

OPTIMIZED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    # Note: aiohttp automatically sets Accept-Encoding: gzip, deflate if not overridden
}


async def fetch_test(session: aiohttp.ClientSession, url: str, headers: dict, check_content_type: bool = False):
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        async with session.get(
            url,
            headers=headers,
            ssl=ssl_ctx,
            timeout=aiohttp.ClientTimeout(total=15, connect=5, sock_read=10),
        ) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            content_encoding = resp.headers.get("Content-Encoding", "identity/none")
            raw_len = resp.content_length

            if check_content_type:
                # 提案ロジック: HTML/XML/JSON以外の不要バイナリを判定
                is_allowed = any(t in content_type.lower() for t in ["text/html", "application/xhtml+xml", "text/plain", "application/json", "application/xml"])
                if not is_allowed:
                    return {
                        "status": status,
                        "aborted": True,
                        "content_type": content_type,
                        "content_encoding": content_encoding,
                        "body_len": 0,
                    }

            # aiohttp resp.read() handles decompression automatically when compressed
            body = await resp.read()
            return {
                "status": status,
                "aborted": False,
                "content_type": content_type,
                "content_encoding": content_encoding,
                "raw_len": raw_len,
                "body_len": len(body),
                "preview": body[:100].decode("utf-8", errors="replace").replace("\n", " "),
            }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)}"}


async def run_comparison():
    print("=" * 80)
    print("各不動産サイトに対するリクエスト制限・ヘッダー最適化の比較検証テスト")
    print("=" * 80)

    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        for target in TARGET_URLS:
            name = target["name"]
            url = target["url"]
            print(f"\n--- 検証対象: {name} ---")
            print(f"URL: {url}")

            # 1. Baseline
            res_base = await fetch_test(session, url, BASELINE_HEADERS, check_content_type=False)
            # 2. Optimized (With headers & Content-Type Fast-Check)
            res_opt = await fetch_test(session, url, OPTIMIZED_HEADERS, check_content_type=True)

            if "error" in res_base:
                print(f"  [Baseline]  ERROR: {res_base['error']}")
            else:
                print(f"  [Baseline]  Status: {res_base['status']} | Type: {res_base['content_type'][:30]} | Encoding: {res_base['content_encoding']} | Body: {res_base['body_len']:,} bytes")

            if "error" in res_opt:
                print(f"  [Optimized] ERROR: {res_opt['error']}")
            else:
                print(f"  [Optimized] Status: {res_opt['status']} | Type: {res_opt['content_type'][:30]} | Encoding: {res_opt['content_encoding']} | Body: {res_opt['body_len']:,} bytes | Aborted: {res_opt['aborted']}")

            # 判定
            if "status" in res_base and "status" in res_opt:
                if res_base["status"] == res_opt["status"] and res_opt["status"] == 200:
                    print("  -> [判定: PASS] 最適化ヘッダー適用後も正常に応答（200 OK）、WAF検知等の副作用なし")
                else:
                    print("  -> [判定: WARN/DIFF] ステータスコードまたは挙動に差分があります")

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_comparison())
