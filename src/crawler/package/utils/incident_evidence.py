"""Structured incident evidence dumper and postmortem draft generator (Chapter 15.6)."""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class IncidentContext:
    reason: str
    last_url: str = ""
    db_ok: bool = True
    http_429_count: int = 0
    active_threads: list[str] = field(default_factory=list)


def dump_incident_evidence(ctx: IncidentContext, output_path: Path) -> None:
    """Write structured incident snapshot to JSON."""
    payload = asdict(ctx)
    payload["captured_at"] = datetime.now(timezone.utc).isoformat()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_postmortem_markdown(ctx: IncidentContext) -> str:
    """Generate a Blameless Postmortem draft from captured evidence."""
    threads = ", ".join(ctx.active_threads) if ctx.active_threads else "none"
    return (
        f"# Incident Postmortem Draft: {ctx.reason}\n\n"
        f"- **Last URL**: {ctx.last_url or 'N/A'}\n"
        f"- **DB Reachable**: {ctx.db_ok}\n"
        f"- **HTTP 429 Count**: {ctx.http_429_count}\n"
        f"- **Active Threads**: {threads}\n"
    )
