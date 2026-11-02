"""
マンションレビュー（mansion-review.jp）連携モジュール (Issue #1197)

区分マンション・一棟マンション等の物件名および所在地から、
マンションレビューの相場坪単価・推定適正価格・過去販売履歴テーブルを取得し、
プロ鑑定プロンプトに注入するための客観取引事例データを生成する。
"""

import logging
import re
import urllib.parse
import urllib.request
from typing import Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# インメモリ簡易キャッシュ (物件名 -> データ)
_MANSION_REVIEW_CACHE: dict[str, dict[str, Any]] = {}


def fetch_mansion_review_data(mansion_name: str, timeout: int = 5) -> dict[str, Any] | None:
    """
    マンション名からマンションレビューの個別ページを検索し、
    推定適正価格、相場坪単価、過去の販売履歴サマリを抽出する。
    """
    if not mansion_name or len(mansion_name.strip()) < 2:
        return None

    clean_name = re.sub(r'[\s　]+', ' ', mansion_name).strip()
    # 部屋番号や号室、階数を除去（例: "パークシティ武蔵小山 301号室" -> "パークシティ武蔵小山"）
    clean_name = re.sub(r'\s*\d+号室.*$', '', clean_name)
    clean_name = re.sub(r'\s*\d+F.*$', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s*\d+階.*$', '', clean_name)
    clean_name = clean_name.strip()

    if clean_name in _MANSION_REVIEW_CACHE:
        return _MANSION_REVIEW_CACHE[clean_name]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    try:
        # 1. 検索リクエスト
        search_url = "https://www.mansion-review.jp/mansion/"
        params = {"mname": clean_name, "search": "1"}
        full_url = f"{search_url}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        soup = BeautifulSoup(html, "html.parser")
        mansion_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.match(r"^https?://www\.mansion-review\.jp/mansion/\d+\.html$", href):
                mansion_url = href
                break

        if not mansion_url:
            logger.debug("No mansion-review detail page found for: %s", clean_name)
            _MANSION_REVIEW_CACHE[clean_name] = {}
            return None

        # 2. 詳細ページ取得
        req_detail = urllib.request.Request(mansion_url, headers=headers)
        with urllib.request.urlopen(req_detail, timeout=timeout) as resp_detail:
            detail_html = resp_detail.read().decode("utf-8", errors="replace")

        dsoup = BeautifulSoup(detail_html, "html.parser")

        tekisei_price = None
        tsubo_price = None
        sqm_price = None

        for text in dsoup.stripped_strings:
            if "推定適正価格" in text and "万円" in text and not tekisei_price:
                m = re.search(r"推定適正価格\s*([0-9,]+)\s*万円", text)
                if m:
                    tekisei_price = m.group(1).replace(",", "")
            if "推定相場坪単価" in text and "万円" in text and not tsubo_price:
                m = re.search(r"推定相場坪単価\s*([0-9,]+)\s*万円", text)
                if m:
                    tsubo_price = m.group(1).replace(",", "")
            if "推定相場㎡単価" in text and "万円" in text and not sqm_price:
                m = re.search(r"推定相場[㎡m2]+単価\s*([0-9,]+)\s*万円", text)
                if m:
                    sqm_price = m.group(1).replace(",", "")

        # 過去販売履歴テーブルのサマリ抽出
        history_rows = []
        for table in dsoup.find_all("table"):
            ttext = table.get_text()
            if "販売価格" in ttext and ("専有面積" in ttext or "階" in ttext):
                for tr in table.find_all("tr")[1:5]:
                    cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(cols) >= 5:
                        # 例: 31階 / 2LDK / 65m2 / 8500万円
                        history_rows.append(" | ".join([c for c in cols[:7] if c and c != "-"]))
                if history_rows:
                    break

        result = {
            "mansion_name": clean_name,
            "url": mansion_url,
            "estimated_market_price_man": int(tekisei_price) if tekisei_price and tekisei_price.isdigit() else None,
            "estimated_tsubo_price_man": int(tsubo_price) if tsubo_price and tsubo_price.isdigit() else None,
            "estimated_sqm_price_man": int(sqm_price) if sqm_price and sqm_price.isdigit() else None,
            "history_samples": history_rows[:3]
        }

        _MANSION_REVIEW_CACHE[clean_name] = result
        return result

    except Exception as e:
        logger.debug("Failed to fetch mansion-review data for %s: %s", clean_name, e)
        return None
