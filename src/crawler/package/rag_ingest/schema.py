"""RAG チャンクのスキーマ検証と quarantine 判定。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CATEGORIES = frozenset({
    "law", "guideline", "tax", "statistics", "hazard", "case_law", "market_report",
    "practitioner_insight", "own_decision_log", "own_model_feedback",
})
KINDS = frozenset({"fact", "judgement"})


@dataclass
class KnowledgeChunk:
    id: str
    source_id: str
    category: str
    title: str
    url: str
    body_text: str
    license: str
    fetched_at: str
    valid_from: str = ""
    valid_to: str = ""
    region: str = ""
    kind: str = "fact"
    speaker_role: str = ""
    confidence: float = 1.0
    summary_only: bool = False
    target_types: list[str] = field(default_factory=list)
    essence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_chunk(chunk: KnowledgeChunk) -> list[str]:
    """不備の一覧を返す。空なら有効。"""
    errors: list[str] = []
    if chunk.category not in CATEGORIES:
        errors.append(f"invalid category: {chunk.category}")
    if chunk.kind not in KINDS:
        errors.append(f"invalid kind: {chunk.kind}")
    for name in ("id", "source_id", "url", "license", "fetched_at", "body_text"):
        if not getattr(chunk, name):
            errors.append(f"missing {name}")
    return errors


UNVERIFIED_LICENSE = "未確認(規約確認待ち)"


def fill_license(chunk: KnowledgeChunk) -> KnowledgeChunk:
    """license が空なら未確認ラベルを補い、信頼度を 0.5 以下に下げる（規約確認後に更新する）。"""
    if not chunk.license:
        chunk.license = UNVERIFIED_LICENSE
        chunk.confidence = min(chunk.confidence, 0.5)
    return chunk


def destination(chunk: KnowledgeChunk) -> str:
    """ライセンス・出典が欠けるチャンクは quarantine、それ以外は curated/<category>。"""
    if validate_chunk(chunk):
        return "quarantine"
    return f"curated/{chunk.category}"