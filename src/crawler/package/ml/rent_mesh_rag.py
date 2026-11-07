"""
全国賃料・需給メッシュ RAG 検索モジュール (Issue #1323)

蓄積された賃料・需給メッシュのRAGナレッジ（GCS: rag/curated/statistics/ または ローカルキャッシュ）から、
物件の所在地（都道府県、市区町村、町丁目）や最寄り駅にマッチする最新の相場・需給チャンクを高速検索し、
AI定性評価（report_generator）へのプロンプト注入用テキストを構築する。
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_RENT_MESH_CACHE: list[dict[str, Any]] | None = None


def clear_rent_mesh_cache() -> None:
    """テスト時等のためのキャッシュクリア。"""
    global _RENT_MESH_CACHE
    _RENT_MESH_CACHE = None


def _read_jsonl_file(fpath: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    rows.append(json.loads(line_str))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed reading rent mesh file %s: %s", fpath, e)
    return rows


def _load_rent_mesh_from_local() -> list[dict[str, Any]]:
    candidate_dirs = [
        "src/crawler/data/rag/curated/statistics",
        "data/rag/curated/statistics",
        "../../tmp_rag_out/rag/curated/statistics",
    ]
    items: list[dict[str, Any]] = []
    for d in candidate_dirs:
        if not os.path.exists(d):
            continue
        matched_files = glob.glob(os.path.join(d, "*.jsonl")) + glob.glob(os.path.join(d, "**", "*.jsonl"), recursive=True)
        for fpath in matched_files:
            items.extend(_read_jsonl_file(fpath))
        if items:
            return items
    return []


def _parse_jsonl_content(content: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in content.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        try:
            items.append(json.loads(line_str))
        except json.JSONDecodeError:
            continue
    return items


def _load_rent_mesh_from_gcs() -> list[dict[str, Any]]:
    gcs_bucket = os.getenv("GCS_BUCKET_NAME", "realestate-images-sumifu-prod")
    if not gcs_bucket:
        return []
    try:
        from google.auth.exceptions import GoogleAuthError
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        items: list[dict[str, Any]] = []
        for blob in bucket.list_blobs(prefix="rag/curated/statistics/"):
            if blob.name.endswith(".jsonl"):
                content = blob.download_as_text(encoding="utf-8")
                items.extend(_parse_jsonl_content(content))
        return items
    except (OSError, RuntimeError, GoogleAuthError) as e:
        logger.warning("GCS rent mesh fetch failed: %s", e)
        return []


def load_rent_mesh_knowledge_base() -> list[dict[str, Any]]:
    """ローカルまたはGCSから賃料メッシュ知識をロードしてメモリにキャッシュする。"""
    global _RENT_MESH_CACHE
    if _RENT_MESH_CACHE is not None:
        return _RENT_MESH_CACHE

    items = _load_rent_mesh_from_local()
    if not items:
        items = _load_rent_mesh_from_gcs()

    _RENT_MESH_CACHE = items
    return _RENT_MESH_CACHE


def _score_chunk_match(
    chunk: dict[str, Any],
    prefecture: str,
    city: str,
    station: str,
) -> float:
    meta = chunk.get("metadata", {})
    chunk_pref = meta.get("prefecture", "")
    chunk_city = meta.get("city", "")
    chunk_station = meta.get("station", "")
    region = chunk.get("region", "")
    title = chunk.get("title", "")

    score = 0.0

    # 都道府県一致
    if prefecture and (prefecture in chunk_pref or prefecture in region or prefecture in title):
        score += 10.0
    elif prefecture:
        # 都道府県不一致なら候補から除外
        return 0.0

    # 駅一致（最高解像度）
    clean_station = re.sub(r"駅$", "", station or "").strip()
    if clean_station and (clean_station in chunk_station or clean_station in region or clean_station in title):
        score += 50.0

    # 市区町村一致
    if city and (city in chunk_city or city in region or city in title):
        score += 20.0

    return score


def search_rent_mesh_knowledge(
    prefecture: str = "",
    city: str = "",
    station: str = "",
    top_k: int = 2,
) -> list[dict[str, Any]]:
    """
    物件の都道府県・市区町村・駅情報に基づき、最も関連度の高い賃料・需給メッシュチャンクを検索する。
    """
    kb = load_rent_mesh_knowledge_base()
    if not kb:
        return []

    scored_items: list[tuple[float, dict[str, Any]]] = []
    for chunk in kb:
        score = _score_chunk_match(chunk, prefecture, city, station)
        if score > 0:
            scored_items.append((score, chunk))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_items[:top_k]]


def format_rent_mesh_context(rent_mesh_items: list[dict[str, Any]]) -> str:
    """プロンプトに注入する周辺賃料相場・需給メッシュテキストを構築する。"""
    if not rent_mesh_items:
        return ""

    lines = ["【周辺賃料相場・需給メッシュ（統計RAG）】"]
    for item in rent_mesh_items:
        title = item.get("title", "相場情報")
        essence = item.get("essence", "")
        body = item.get("body_text", "")
        lines.append(f"・《{title}》")
        if essence:
            lines.append(f"  概要: {essence}")
        if body:
            # 長大化防止のため先頭600文字
            lines.append(f"  詳細:\n{body[:600]}")

    return "\n".join(lines)
