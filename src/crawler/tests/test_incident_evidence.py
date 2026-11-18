import json
from package.utils.incident_evidence import IncidentContext, build_postmortem_markdown, dump_incident_evidence


def test_dump_incident_evidence_and_postmortem(tmp_path):
    ctx = IncidentContext(
        reason="worker_timeout",
        last_url="https://example.com/list?page=3",
        db_ok=False,
        http_429_count=12,
        active_threads=["Thread-1", "Thread-2"],
    )
    out_file = tmp_path / "evidence.json"
    dump_incident_evidence(ctx, out_file)
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["reason"] == "worker_timeout"
    assert data["db_ok"] is False
    assert data["http_429_count"] == 12

    md = build_postmortem_markdown(ctx)
    assert "worker_timeout" in md
    assert "https://example.com/list?page=3" in md
    assert "False" in md
