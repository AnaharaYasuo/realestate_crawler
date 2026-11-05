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
        from google.auth.exceptions import GoogleAuthError
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
    except (OSError, RuntimeError, GoogleAuthError) as e:
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


_KEYWORDS = [
    # 建築・敷地・道路・容積
    "接道", "道路", "斜線", "日影", "建蔽率", "容積率", "がけ", "崖", "擁壁",
    "土砂災害", "浸水", "市街化調整区域", "市街化区域", "用途地域", "防火", "準防火",
    "特例", "地区計画", "建築確認", "不燃化", "地下室", "構造", "耐震",
    # 借地借家・契約・権利
    "借地", "借家", "定期借地", "定期借家", "更新料", "明渡", "賃料", "借主", "貸主",
    # 税務・減税・特例
    "住宅ローン控除", "登録免許税", "不動産取得税", "固定資産税", "都市計画税",
    "譲渡所得", "特別控除", "損益通算", "減価償却", "耐用年数", "青色申告",
    # 鑑定評価・価格形成
    "鑑定評価", "最有効使用", "正常価格", "積算価格", "収益還元", "比準価格",
    "取引事例", "地域要因", "個別的要因", "画地", "市場性",
]


def _score_law_item(item: dict[str, Any], query_lower: str, region_key: str = "") -> int:
    score = 0
    item_region = item.get("region", "")
    # 地域マッチング（横浜市、千葉市など）
    if region_key and item_region:
        if region_key in item_region or item_region in region_key:
            score += 15
        elif item_region != "national":
            # 他都市の条例は除外
            return 0

    title = item.get("title", "")
    body = item.get("body_text", "")
    haystack = (title + " " + body).lower()

    for kw in _KEYWORDS:
        if kw in query_lower and kw in haystack:
            score += 3
            if kw in title:
                score += 5

    return score


def search_legal_knowledge(
    query_text: str, region_key: str = "", top_k: int = 5, diversify_categories: bool = True
) -> list[dict[str, Any]]:
    """
    物件情報（所在地・道路・容積・構造・価格・種別等）から、関係する法令条文・都市部特例条例・鑑定基準・税制を総動員抽出。
    diversify_categories=True の場合、条例・建築都市法・税法・鑑定基準からバランスよく多面抽出する。
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

    if not diversify_categories or len(scored) <= top_k:
        return [item for _, item in scored[:top_k]]

    # カテゴリ・ソース別分散抽出（特定条例だけに偏らず、全国法・税法・鑑定基準を総動員）
    selected = []
    source_counts: dict[str, int] = {}
    for _, item in scored:
        sid = item.get("source_id", "")
        # 同一法令・条例からは最大2条までに制限し、多様な法令・条例を総動員
        count = source_counts.get(sid, 0)
        if count < 2:
            selected.append(item)
            source_counts[sid] = count + 1
            if len(selected) >= top_k:
                break

    # 足りない場合はスコア順で埋める
    if len(selected) < top_k:
        for _, item in scored:
            if item not in selected:
                selected.append(item)
                if len(selected) >= top_k:
                    break

    return selected
