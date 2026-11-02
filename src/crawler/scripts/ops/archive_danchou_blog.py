"""
元祖狼旅団ブログ全記事（約3000記事）HTMLアーカイブ ＆ ナレッジベース構築ワンタイムスクリプト
(Issue #1191)

元祖ブログ（http://siokaraiookami.blog.fc2.com/）の全アーカイブから記事URLを網羅抽出し、
生HTMLをGCS (gs://realestate-images-sumifu-prod/danchou_raw_html/) に保存するとともに、
本文テキスト・タイトル・カテゴリ・キーワードを抽出した danchou_kb_full.jsonl を生成する。
"""

import asyncio
import json
import logging
import os
import re
from typing import Any
import aiohttp
from bs4 import BeautifulSoup
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://siokaraiookami.blog.fc2.com/"
GCS_BUCKET_NAME = "realestate-images-sumifu-prod"
RAW_HTML_PREFIX = "danchou_raw_html"
KB_GCS_PATH = "rag/danchou_kb_full.jsonl"
LOCAL_KB_PATH = "src/crawler/data/rag/danchou_kb_full.jsonl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TYPE_KEYWORDS = {
    "区分マンション": ["区分", "マンション", "修繕積立金", "専有部", "管理規約", "給排水管"],
    "一棟アパート": ["アパート", "一棟", "レントロール", "満室", "空室", "客付け", "利回り", "プロパン"],
    "戸建": ["戸建", "戸建て", "ボロ戸建", "雨漏り", "汲み取り", "下水", "シロアリ", "diy"],
    "土地": ["土地", "更地", "建築条件", "確定測量", "境界", "水道管", "引込", "擁壁", "セットバック"]
}


async def fetch_url(session: aiohttp.ClientSession, url: str, sem: asyncio.Semaphore) -> tuple[str, bytes | None]:
    async with sem:
        for retry in range(3):
            try:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        return url, content
                    if resp.status == 404:
                        return url, None
            except Exception as e:
                if retry == 2:
                    logger.warning("Failed to fetch %s: %s", url, e)
                await asyncio.sleep(1 + retry)
        return url, None


async def collect_all_entry_urls(session: aiohttp.ClientSession, sem: asyncio.Semaphore) -> list[str]:
    """トップページから月別アーカイブURLを抽出し、全記事URLを取得する"""
    logger.info("Collecting monthly archive URLs from top page...")
    _, top_html = await fetch_url(session, BASE_URL, sem)
    if not top_html:
        raise RuntimeError("Failed to fetch blog top page")

    soup = BeautifulSoup(top_html.decode("utf-8", errors="ignore"), "html.parser")
    month_urls = sorted({
        a["href"] for a in soup.find_all("a", href=True)
        if re.search(r"blog-date-\d+\.html", a["href"])
    })
    logger.info("Found %d monthly archive pages.", len(month_urls))

    entry_urls = set()
    tasks = [fetch_url(session, m_url, sem) for m_url in month_urls]
    results = await asyncio.gather(*tasks)

    for m_url, m_html in results:
        if not m_html:
            continue
        m_soup = BeautifulSoup(m_html.decode("utf-8", errors="ignore"), "html.parser")
        for a in m_soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"blog-entry-\d+\.html$", href):
                entry_urls.add(href)

    logger.info("Total unique blog entries discovered: %d", len(entry_urls))
    return sorted(entry_urls, key=lambda x: int(re.search(r"blog-entry-(\d+)\.html$", x).group(1)), reverse=True)


def parse_entry_html(url: str, raw_bytes: bytes) -> dict[str, Any] | None:
    try:
        html = raw_bytes.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        m = re.search(r"blog-entry-(\d+)\.html$", url)
        entry_id = int(m.group(1)) if m else 0

        title_elem = soup.find(["h2", "h3"], class_=re.compile(r"entry_header|entry_title|title", re.IGNORECASE)) or soup.find("h3") or soup.title
        title = title_elem.get_text().strip() if title_elem else f"Entry {entry_id}"
        title = re.sub(r"\s+", " ", title)

        body_elem = soup.find("div", class_=re.compile(r"entry_body|entry-body|main_content", re.IGNORECASE))
        if not body_elem:
            body_elem = soup.find("div", id=re.compile(r"entry", re.IGNORECASE)) or soup.body

        if not body_elem:
            return None

        # クローンを作成して不要タグを除去
        for tag in body_elem(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
            tag.decompose()

        # 改行と段落を考慮してテキスト化
        raw_text = body_elem.get_text(separator="\n")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        clean_lines = []
        for line in lines:
            # バナーや投票定型文の除去
            if any(b in line for b in ["ポチっと押すと", "FC2 Blog Ranking", "FC2ブログ", "拍手する", "ブログランキング"]):
                continue
            clean_lines.append(line)

        body_text = "\n".join(clean_lines)
        if len(body_text) < 50:
            return None

        # target_types 判定
        target_types = []
        for ptype, kws in TYPE_KEYWORDS.items():
            if any(kw in body_text for kw in kws):
                target_types.append(ptype)
        if not target_types:
            target_types = ["全般・実戦哲学"]

        essence = clean_lines[0] if clean_lines else title
        for line in clean_lines[:15]:
            if any(k in line for k in ["いいか", "素人", "指値", "利回り", "積算", "罠", "リアル", "命", "鉄則", "法則", "買主", "売主", "買い付け"]) and len(line) > 15:
                    essence = line
                    break

        return {
            "id": f"entry_{entry_id}",
            "entry_id": entry_id,
            "title": title,
            "url": url,
            "target_types": target_types,
            "essence": essence[:300],
            "body_text": body_text[:2500]
        }
    except Exception as e:
        logger.debug("Failed to parse %s: %s", url, e)
        return None


async def run_archive_and_build_kb(limit: int | None = None):
    sem = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=20, ssl=False)

    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    async with aiohttp.ClientSession(connector=connector) as session:
        urls = await collect_all_entry_urls(session, sem)
        if limit:
            urls = urls[:limit]

        logger.info("Starting crawl and GCS upload for %d entries...", len(urls))

        kb_records = []
        uploaded_count = 0

        # バッチ単位（50件ずつ）で取得・アップロード
        chunk_size = 50
        for i in range(0, len(urls), chunk_size):
            chunk_urls = urls[i:i + chunk_size]
            tasks = [fetch_url(session, u, sem) for u in chunk_urls]
            results = await asyncio.gather(*tasks)

            for url, raw_bytes in results:
                if not raw_bytes:
                    continue

                m = re.search(r"blog-entry-(\d+)\.html$", url)
                entry_id = m.group(1) if m else "unknown"

                # 1. 生HTMLをGCSに保存
                blob_name = f"{RAW_HTML_PREFIX}/blog-entry-{entry_id}.html"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(raw_bytes, content_type="text/html; charset=utf-8")
                uploaded_count += 1

                # 2. ナレッジレコード抽出
                parsed = parse_entry_html(url, raw_bytes)
                if parsed:
                    kb_records.append(parsed)

            logger.info("Processed %d / %d entries (Uploaded: %d, KB records: %d)", min(i + chunk_size, len(urls)), len(urls), uploaded_count, len(kb_records))
            await asyncio.sleep(0.5)

        logger.info("All HTMLs uploaded to GCS. Total KB records: %d", len(kb_records))

        # 3. KB JSONL 保存（ローカルおよびGCS）
        os.makedirs(os.path.dirname(LOCAL_KB_PATH), exist_ok=True)
        jsonl_str = "\n".join([json.dumps(r, ensure_ascii=False) for r in kb_records])
        with open(LOCAL_KB_PATH, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write(jsonl_str)
        logger.info("Saved local KB to %s", LOCAL_KB_PATH)

        kb_blob = bucket.blob(KB_GCS_PATH)
        kb_blob.upload_from_string(jsonl_str.encode("utf-8"), content_type="application/x-ndjson")
        logger.info("Uploaded full KB to gs://%s/%s", GCS_BUCKET_NAME, KB_GCS_PATH)


if __name__ == "__main__":
    asyncio.run(run_archive_and_build_kb())
