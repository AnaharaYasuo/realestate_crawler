"""e-Gov 法令API v2 から法令を条単位でチャンク化する。

利用条件: e-Gov 法令検索の法令データは政府標準利用規約（CC BY 4.0 互換）。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from package.rag_ingest.schema import KnowledgeChunk

API = "https://laws.e-gov.go.jp/api/2/law_data/{law_id}"
LICENSE = "政府標準利用規約2.0(CC BY 4.0互換)"
USER_AGENT = "realestate-rag-ingest/1.0"

# 不動産評価に関わる主要法令（law_id）
TARGET_LAWS = {
    "325AC0000000201": "建築基準法",
    "343AC0000000100": "都市計画法",
    "327AC1000000176": "宅地建物取引業法",
    "403AC0000000090": "借地借家法",
    "337AC0000000069": "建物の区分所有等に関する法律",
    "416AC0000000123": "不動産登記法",
    "336AC0000000191": "宅地造成及び特定盛土等規制法",
    "129AC0000000089": "民法",
}


def node_text(node: Any) -> str:
    if isinstance(node, str):
        return node
    return "".join(node_text(c) for c in node.get("children", []))


def iter_articles(node: Any):
    if isinstance(node, dict):
        if node.get("tag") == "Article":
            yield node
            return
        for c in node.get("children", []):
            yield from iter_articles(c)


def _child_text(article: dict, tag: str) -> str:
    return "".join(node_text(c) for c in article.get("children", []) if isinstance(c, dict) and c.get("tag") == tag)


def article_to_chunks(law_id: str, law_title: str, doc: dict, fetched_at: str) -> list[KnowledgeChunk]:
    chunks = []
    url = f"https://laws.e-gov.go.jp/law/{law_id}"
    for art in iter_articles(doc["law_full_text"]):
        num = art.get("attr", {}).get("Num", "")
        title = _child_text(art, "ArticleTitle")
        caption = _child_text(art, "ArticleCaption")
        body = "\n".join(
            node_text(c) for c in art.get("children", [])
            if isinstance(c, dict) and c.get("tag") in ("Paragraph", "Item")
        ).strip()
        if not body:
            continue
        chunks.append(KnowledgeChunk(
            id=f"law_{law_id}_{num}", source_id=f"egov_{law_id}", category="law",
            title=f"{law_title} {title}{caption}".strip(), url=f"{url}#Mp-At_{num}",
            body_text=body, license=LICENSE, fetched_at=fetched_at, kind="fact",
            speaker_role="statute", confidence=1.0, essence=caption.strip("（）"),
        ))
    return chunks


def fetch_law(law_id: str, session: requests.Session | None = None) -> dict:
    s = session or requests.Session()
    r = s.get(API.format(law_id=law_id), params={"law_full_text_format": "json"},
              headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r.json()


def collect(law_ids: dict[str, str] | None = None, delay: float = 1.0) -> dict[str, list[KnowledgeChunk]]:
    now = datetime.now(timezone.utc).isoformat()
    result: dict[str, list[KnowledgeChunk]] = {}
    with requests.Session() as s:
        for law_id, title in (law_ids or TARGET_LAWS).items():
            result[f"egov_{law_id}"] = article_to_chunks(law_id, title, fetch_law(law_id, s), now)
            time.sleep(delay)
    return result