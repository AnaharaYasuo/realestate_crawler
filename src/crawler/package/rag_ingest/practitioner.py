"""実務家の知見（判断ログ・取材メモ・書き起こし）の取り込み。

入力は JSONL（1行1知見）。必須: text, source_url。推奨: kind, speaker_role, region,
valid_to, license, category(practitioner_insight|own_decision_log)。
license が空の行は自社作成として DEFAULT_LICENSE を補う。不備（出典URL・本文・category 不正など）は quarantine。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from package.rag_ingest.schema import KnowledgeChunk

DEFAULT_LICENSE = "社内利用(自社作成)"


def load_insights(path: str, source_id: str) -> list[KnowledgeChunk]:
    now = datetime.now(UTC).isoformat()
    chunks = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        text = r.get("text", "").strip()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        chunks.append(KnowledgeChunk(
            id=f"{source_id}_{digest}", source_id=source_id,
            category=r.get("category", "practitioner_insight"),
            title=r.get("title", text[:30]), url=r.get("source_url", ""), body_text=text,
            license=r.get("license") or DEFAULT_LICENSE, fetched_at=now, valid_from=r.get("valid_from", ""),
            valid_to=r.get("valid_to", ""), region=r.get("region", ""),
            kind=r.get("kind", "judgement"), speaker_role=r.get("speaker_role", ""),
            confidence=float(r.get("confidence", 0.5)), summary_only=True,
            target_types=r.get("target_types", []), essence=r.get("essence", ""),
        ))
    return chunks