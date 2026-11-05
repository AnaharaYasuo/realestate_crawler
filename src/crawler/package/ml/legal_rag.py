"""
法的規制・都市特例・鑑定評価基準の法令知識検索（RAGモジュール）
"""
from __future__ import annotations

import glob
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_LAW_CACHE: list[dict[str, Any]] | None = None


def _read_jsonl_file(fpath: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed reading law file %s: %s", fpath, e)
    return rows


def _load_laws_from_local() -> list[dict[str, Any]]:
    candidate_dirs = [
        "../../tmp_rag_out/rag/curated/law",
        "src/crawler/data/rag/curated/law",
        "data/rag/curated/law",
    ]
    for d in candidate_dirs:
        matched_files = glob.glob(os.path.join(d, "*.jsonl"))
        if not matched_files:
            continue
        items: list[dict[str, Any]] = []
        for fpath in matched_files:
            items.extend(_read_jsonl_file(fpath))
        if items:
            return items
    return []


def _load_laws_from_gcs() -> list[dict[str, Any]]:
    gcs_bucket = os.getenv("GCS_BUCKET_NAME", "realestate-images-sumifu-prod")
    if not gcs_bucket:
        return []
    items: list[dict[str, Any]] = []
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        blobs = list(client.list_blobs(bucket, prefix="rag/curated/law/"))
        for b in blobs:
            if not b.name.endswith(".jsonl"):
                continue
            text = b.download_as_text(encoding="utf-8")
            for line in text.splitlines():
                if line.strip():
                    items.append(json.loads(line))
    except (OSError, RuntimeError) as e:
        logger.warning("GCS law retrieval fallback failed: %s", e)
    return items


def load_curated_laws() -> list[dict[str, Any]]:
    global _LAW_CACHE
    if _LAW_CACHE is not None:
        return _LAW_CACHE

    items = _load_laws_from_local()
    if not items:
        items = _load_laws_from_gcs()

    _LAW_CACHE = items
    return _LAW_CACHE


def _score_law_item(item: dict[str, Any], query_lower: str, region_key: str = "") -> int:
    score = 0
    item_region = item.get("region", "")
    # 地域マッチング（横浜市、千葉市など）
    if region_key and item_region:
        if region_key in item_region or item_region in region_key:
            score += 10
        elif item_region != "national":
            # 他都市の条例は減点
            return 0

    title = item.get("title", "")
    body = item.get("body_text", "")
    haystack = (title + " " + body).lower()

    # 主要キーワードマッチ
    keywords = [
        "接道", "道路", "斜線", "日影", "建蔽率", "容積率", "がけ", "崖", "擁壁",
        "土砂災害", "浸水", "市街化調整区域", "用途地域", "防火", "準防火",
        "特例", "地区計画", "建築確認", "不燃化", "地下室", "鑑定評価",
    ]
    for kw in keywords:
        if kw in query_lower and kw in haystack:
            score += 3
            if kw in title:
                score += 5

    return score


def search_legal_knowledge(query_text: str, region_key: str = "", top_k: int = 3) -> list[dict[str, Any]]:
    """
    物件情報（所在地・道路・容積・構造等）から、関係する法令条文・都市部特例条例を抽出
    """
    laws = load_curated_laws()
    if not laws:
        return []

    query_lower = query_text.lower()
    scored = []
    for item in laws:
        s = _score_law_item(item, query_lower, region_key)
        if s > 0:
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k]]
