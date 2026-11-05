"""e-Gov 法令API v2 から法令を条単位でチャンク化する。

利用条件: e-Gov 法令検索の法令データは政府標準利用規約（CC BY 4.0 互換）。
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
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
    "325CO0000000338": "建築基準法施行令",
    "325M50004000040": "建築基準法施行規則",
    "344CO0000000158": "都市計画法施行令",
    "344M50004000049": "都市計画法施行規則",
    "339CO0000000383": "宅地建物取引業法施行令",
    "332M50004000012": "宅地建物取引業法施行規則",
    "504M60000010029": "借地借家法施行規則",
    "416CO0000000379": "不動産登記令",
    "417M60000010018": "不動産登記規則",
    "349AC1000000092": "国土利用計画法",
    "344AC0000000038": "都市再開発法",
    "412AC1000000149": "マンションの管理の適正化の推進に関する法律",
    "426AC1000000127": "空家等対策の推進に関する特別措置法",
    "325AC0000000226": "地方税法",
    "332AC0000000026": "租税特別措置法",
    "325AC0000000073": "相続税法",
    "340AC0000000033": "所得税法",
    "401AC0000000084": "土地基本法",
    "411AC0000000081": "住宅の品質確保の促進等に関する法律",
    "419AC0000000066": "特定住宅瑕疵担保責任の履行の確保等に関する法律",
    "338AC0000000152": "不動産の鑑定評価に関する法律",
    "339CO0000000005": "不動産の鑑定評価に関する法律施行令",
    "339M50004000009": "不動産の鑑定評価に関する法律施行規則",
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
    now = datetime.now(UTC).isoformat()
    result: dict[str, list[KnowledgeChunk]] = {}
    with requests.Session() as s:
        for law_id, title in (law_ids or TARGET_LAWS).items():
            result[f"egov_{law_id}"] = article_to_chunks(law_id, title, fetch_law(law_id, s), now)
            time.sleep(delay)
    return result