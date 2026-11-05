"""チャンクの保存（ローカル JSONL / GCS）と差分判定。"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

from package.rag_ingest.schema import KnowledgeChunk, destination, fill_license


def content_hash(chunk: KnowledgeChunk) -> str:
    return hashlib.sha256(chunk.body_text.encode("utf-8")).hexdigest()


def group_by_destination(chunks: Iterable[KnowledgeChunk]) -> dict[str, list[KnowledgeChunk]]:
    groups: dict[str, list[KnowledgeChunk]] = {}
    for c in chunks:
        fill_license(c)
        groups.setdefault(destination(c), []).append(c)
    return groups


def render_jsonl(chunks: Iterable[KnowledgeChunk]) -> str:
    return "".join(json.dumps(c.to_dict(), ensure_ascii=False) + "\n" for c in chunks)


def write_local(chunks: Iterable[KnowledgeChunk], source_id: str, root: str) -> list[str]:
    """root/rag/<dest>/<source_id>.jsonl に書き出し、書いたパスを返す。"""
    written = []
    for dest, items in group_by_destination(chunks).items():
        path = Path(root) / "rag" / dest / f"{source_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_jsonl(items), encoding="utf-8")
        written.append(str(path))
    return written


def write_gcs(chunks: Iterable[KnowledgeChunk], source_id: str, bucket_name: str | None = None) -> list[str]:
    from google.cloud import storage

    bucket = storage.Client().bucket(bucket_name or os.getenv("GCS_BUCKET_NAME", "realestate-images-sumifu-prod"))
    written = []
    for dest, items in group_by_destination(chunks).items():
        name = f"rag/{dest}/{source_id}.jsonl"
        bucket.blob(name).upload_from_string(render_jsonl(items), content_type="application/x-ndjson")
        written.append(name)
    return written