"""TDD tests for Issue #1849: Bargain notification resilience, Slack failure alerts, and daily Auto-Heal integration."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
JST = datetime.timezone(datetime.timedelta(hours=9))


class _FakeGhClient:
    """In-memory fake GhClientProtocol for sync_auto_heal_issues tests."""

    def __init__(self, open_issues: list[dict] | None = None):
        self.open_issues: list[dict] = list(open_issues or [])
        self.created: list[dict] = []
        self.closed: list[int] = []
        self.comments: list[tuple[int, str]] = []
        self.reopened: list[int] = []
        self._next_num = 2000

    def ensure_labels(self) -> None:
        return None

    def list_open_auto_heal_issues(self) -> list[dict]:
        return list(self.open_issues)

    def list_all_auto_heal_issues(self, limit: int = 300) -> list[dict]:
        return list(self.open_issues)

    def list_open_prs(self) -> list[dict]:
        return []

    def get_issue(self, number: int) -> dict:
        for iss in self.open_issues:
            if iss["number"] == number:
                return iss
        raise KeyError(number)

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        num = self._next_num
        self._next_num += 1
        rec = {"number": num, "title": title, "body": body, "state": "OPEN", "labels": labels, "comments": []}
        self.created.append(rec)
        self.open_issues.append(rec)
        return num

    def update_issue_body(self, number: int, body: str) -> None:
        for iss in self.open_issues:
            if iss["number"] == number:
                iss["body"] = body

    def comment_issue(self, number: int, body: str) -> None:
        self.comments.append((number, body))

    def update_labels(self, number: int, add_labels: list[str], remove_labels: list[str]) -> None:
        return None

    def close_issue(self, number: int, comment: str) -> None:
        self.closed.append(number)
        self.comments.append((number, comment))

    def reopen_issue(self, number: int, comment: str | None = None) -> None:
        self.reopened.append(number)
        if comment:
            self.comments.append((number, comment))


# ---------------------------------------------------------------------------
# 1. Infrastructure resource & timeout guardrails
# ---------------------------------------------------------------------------


def test_ml_pipeline_memory_and_timeout_upgraded_for_mansion_training():
    variables_tf = (REPO_ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    m_mem = re.search(
        r'variable\s+"ml_pipeline_memory"\s*\{[^}]*default\s*=\s*"([^"]+)"',
        variables_tf,
        re.DOTALL,
    )
    assert m_mem is not None
    assert m_mem.group(1) == "4Gi", f"Expected ml_pipeline_memory=4Gi, got {m_mem.group(1)}"

    job_tf = (REPO_ROOT / "terraform" / "cloud_run_job.tf").read_text(encoding="utf-8")
    m_job = re.search(
        r'resource\s+"google_cloud_run_v2_job"\s+"ml_pipeline_job"\s*\{.*?timeout\s*=\s*"(\d+)s"',
        job_tf,
        re.DOTALL,
    )
    assert m_job is not None
    assert int(m_job.group(1)) >= 10800

    from scripts import ensure_resources_stopped

    assert ensure_resources_stopped.JOB_HUNG_THRESHOLD_MAP["realestate-ml-pipeline"] >= 11400.0


# ---------------------------------------------------------------------------
# 2. run_ml_pipeline.py: non-blocking Step 2/5, Slack alerts, auto-heal hook
# ---------------------------------------------------------------------------


def test_run_ml_pipeline_continues_to_recommendations_when_training_ooms_and_alerts():
    from scripts.ops import run_ml_pipeline

    executed_descs: list[str] = []
    auto_heal_failed_steps_args: list[list[str]] = []

    def fake_run_command(cmd: list[str], desc: str):
        executed_descs.append(desc)
        if "auto_heal_parsers.py" in " ".join(cmd) and "--failed-steps" in cmd:
            idx = cmd.index("--failed-steps")
            auto_heal_failed_steps_args.append(json.loads(cmd[idx + 1]))
        if "Step 2/5: ML Model Re-Training" in desc:
            raise RuntimeError(f"Step '{desc}' failed with exit code -9")

    alert_calls: list[str] = []
    dev_calls: list[str] = []
    status_uploads: list[dict] = []

    async def fake_alert(msg: str):
        alert_calls.append(msg)
        return True

    async def fake_dev(msg: str):
        dev_calls.append(msg)
        return True

    with (
        patch.object(run_ml_pipeline, "start_on_demand_resources"),
        patch.object(run_ml_pipeline, "verify_barrier_completion", return_value=(True, [])),
        patch.object(run_ml_pipeline, "send_aggregated_crawl_report", return_value=True),
        patch.object(run_ml_pipeline, "_run_self_healing_recrawl_and_validation"),
        patch.object(run_ml_pipeline, "run_command", side_effect=fake_run_command),
        patch.object(run_ml_pipeline, "send_crawling_summary_alert", side_effect=fake_alert),
        patch.object(run_ml_pipeline, "send_dev_report", side_effect=fake_dev),
        patch.object(run_ml_pipeline, "_write_ml_pipeline_status", side_effect=lambda payload: status_uploads.append(payload)),
        patch.object(run_ml_pipeline, "_can_stop_shared_proxysql", return_value=False),
    ):
        rc = run_ml_pipeline.main(["--train", "--skip-potentials-sync", "--property-type", "mansion"])

    # Training failure must NOT block Step 3/5 (Bulk Eval) and Step 4/5 (Recommendations)
    assert any("Step 3/5: Batch Estimation" in d for d in executed_descs)
    assert any("Step 4/5: Slack Notification" in d for d in executed_descs)
    # Must still return non-zero so Cloud Run reports failure
    assert rc == 1
    # Must alert Slack (#property_alert & #dev-agent)
    assert alert_calls, "Expected Slack alert to #property_alert on ML training failure"
    assert dev_calls, "Expected Slack report to #dev-agent on ML training failure"
    # Must update auto-heal instructions with the failed ML training step
    assert auto_heal_failed_steps_args, "Expected auto_heal_parsers.py to be called with --failed-steps"
    assert any("Step 2/5" in s for s in auto_heal_failed_steps_args[-1])
    # Must persist final ML pipeline status with recommendation_succeeded=True and failed_steps
    assert status_uploads
    final_status = status_uploads[-1]
    assert final_status["status"] == "failed"
    assert final_status["recommendation_succeeded"] is True
    assert any("Step 2/5" in s for s in final_status["failed_steps"])


def test_run_ml_pipeline_alerts_slack_when_barrier_aborts_before_recommendations():
    from scripts.ops import run_ml_pipeline

    alert_calls: list[str] = []
    dev_calls: list[str] = []

    async def fake_alert(msg: str):
        alert_calls.append(msg)
        return True

    async def fake_dev(msg: str):
        dev_calls.append(msg)
        return True

    with (
        patch.object(run_ml_pipeline, "start_on_demand_resources"),
        patch.object(run_ml_pipeline, "run_command"),
        patch.object(run_ml_pipeline, "verify_barrier_completion", return_value=(False, ["0", "1"])),
        patch.object(run_ml_pipeline, "send_aggregated_crawl_report", return_value=True),
        patch.object(run_ml_pipeline, "send_crawling_summary_alert", side_effect=fake_alert),
        patch.object(run_ml_pipeline, "send_dev_report", side_effect=fake_dev),
        patch.object(run_ml_pipeline, "_write_ml_pipeline_status"),
        patch.object(run_ml_pipeline, "_can_stop_shared_proxysql", return_value=False),
    ):
        rc = run_ml_pipeline.main([])

    assert rc == 1
    assert any("割安物件通知" in m for m in alert_calls)
    assert any("割安物件通知" in m for m in dev_calls)


# ---------------------------------------------------------------------------
# 3. send_recommendations.py: GCS heartbeat & all-dispatch-failed alert
# ---------------------------------------------------------------------------


def test_send_recommendations_writes_heartbeat_and_raises_on_all_dispatch_failed():
    from scripts.ops import send_recommendations as sr

    fake_eval = SimpleNamespace(
        id=1,
        property_url="https://example.com/prop/1",
        property_type="mansion",
        company="mitsui",
        investment_rating="AA",
        ai_evaluation_summary="good",
    )
    fake_prop = SimpleNamespace(propertyName="テストマンション", price=30000000)

    recorded_heartbeats: list[dict] = []
    alert_calls: list[str] = []

    async def fake_alert(msg: str):
        alert_calls.append(msg)
        return True

    with (
        patch.object(sr, "close_old_connections"),
        patch.object(sr, "connections"),
        patch.object(sr, "bound_mysql_timeouts"),
        patch.object(sr, "_notify_status"),
        patch.object(sr, "ensure_station_cache"),
        patch.object(sr, "_fetch_recommendation_candidates", return_value=[fake_eval]),
        patch.object(sr, "batch_resolve_properties", return_value={fake_eval.property_url: fake_prop}),
        patch.object(sr, "_evaluate_candidate", return_value=(True, "割安", 90.0)),
        patch.object(sr, "_dispatch_single_recommendation", return_value=False),
        patch.object(sr, "_record_recommendation_heartbeat", side_effect=lambda payload: recorded_heartbeats.append(payload)),
        patch.object(sr, "send_crawling_summary_alert", side_effect=fake_alert),
    ):
        with pytest.raises(RuntimeError, match="Slack"):
            sr.send_recommendations()

    assert recorded_heartbeats
    assert recorded_heartbeats[-1]["status"] == "dispatch_failed"
    assert recorded_heartbeats[-1]["sent_count"] == 0
    assert alert_calls, "Expected Slack alert to #property_alert when all dispatches fail"


# ---------------------------------------------------------------------------
# 4. ensure_resources_stopped.py: Out-of-process watchdog for missed delivery
# ---------------------------------------------------------------------------


def test_safety_net_watchdog_alerts_once_when_recommendation_missing_past_deadline():
    from scripts import ensure_resources_stopped as ers

    now_jst = datetime.datetime(2026, 11, 26, 9, 0, 0, tzinfo=JST)
    stale_rec = {"completed_date_jst": "2026-11-25", "status": "ok"}
    failed_ml = {
        "date_jst": "2026-11-26",
        "status": "failed",
        "recommendation_succeeded": False,
        "failed_steps": ["Step 2/5: ML Model Re-Training [mansion]"],
    }

    stored_blobs: dict[str, dict] = {
        ers.RECOMMENDATION_HEARTBEAT_GCS_KEY: stale_rec,
        ers.ML_PIPELINE_STATUS_GCS_KEY: failed_ml,
    }
    alerts: list[tuple[str, str | None]] = []

    def fake_read(key: str, bucket_name: str | None = None):
        return stored_blobs.get(key)

    def fake_write(key: str, payload: dict, bucket_name: str | None = None):
        stored_blobs[key] = payload
        return True

    with (
        patch.object(ers, "_read_gcs_json", side_effect=fake_read),
        patch.object(ers, "_write_gcs_json", side_effect=fake_write),
        patch.object(ers, "send_slack_alert", side_effect=lambda msg, channel=None: alerts.append((msg, channel))),
    ):
        alerted_first = ers.check_daily_recommendation_delivery(
            active_ml_jobs=[],
            now_jst=now_jst,
        )
        # Second hourly run on same day must be deduplicated
        alerted_second = ers.check_daily_recommendation_delivery(
            active_ml_jobs=[],
            now_jst=now_jst + datetime.timedelta(hours=1),
        )

    assert alerted_first is True
    assert alerted_second is False
    assert len(alerts) >= 2  # #property_alert and #dev-agent
    assert any("割安物件通知" in msg for msg, _ in alerts)


def test_safety_net_watchdog_does_not_alert_when_delivered_today():
    from scripts import ensure_resources_stopped as ers

    now_jst = datetime.datetime(2026, 11, 26, 9, 0, 0, tzinfo=JST)
    ok_rec = {"completed_date_jst": "2026-11-26", "status": "ok", "sent_count": 12}
    alerts: list[str] = []

    with (
        patch.object(ers, "_read_gcs_json", side_effect=lambda key, bucket_name=None: ok_rec if key == ers.RECOMMENDATION_HEARTBEAT_GCS_KEY else None),
        patch.object(ers, "_write_gcs_json", return_value=True),
        patch.object(ers, "send_slack_alert", side_effect=lambda msg, channel=None: alerts.append(msg)),
    ):
        alerted = ers.check_daily_recommendation_delivery(active_ml_jobs=[], now_jst=now_jst)

    assert alerted is False
    assert alerts == []


# ---------------------------------------------------------------------------
# 5. sync_auto_heal_issues.py & workflow: Daily Auto-Heal coverage
# ---------------------------------------------------------------------------


def test_sync_auto_heal_issues_creates_issue_on_missing_recommendation_and_closes_when_recovered():
    from scripts.ops import sync_auto_heal_issues as sahi

    now_jst = datetime.datetime(2026, 11, 26, 7, 30, 0, tzinfo=JST)
    base_instruction = {
        "generated_at": "2026-11-25 21:18:50",
        "failed_pipeline_steps": [],
        "targets": [],
        "ai_summary": "test",
    }
    stale_rec = {"completed_date_jst": "2026-11-25", "status": "ok"}
    failed_ml = {
        "date_jst": "2026-11-26",
        "status": "failed",
        "recommendation_succeeded": False,
        "failed_steps": ["Step 2/5: ML Model Re-Training [mansion] failed with exit code -9"],
    }

    enriched = sahi.enrich_instruction_with_delivery_health(
        base_instruction,
        rec_heartbeat=stale_rec,
        ml_status=failed_ml,
        now_jst=now_jst,
    )
    gh = _FakeGhClient()
    res1 = sahi.sync_instruction_to_issues(enriched, gh)
    assert res1["created"], "Expected an auto-heal Issue to be created for missed bargain recommendation"
    created_keys = [sahi._extract_issue_key(c["body"]) for c in gh.created]
    assert sahi.BARGAIN_NOT_DELIVERED_KEY in created_keys

    # Next run after recovery: recommendation delivered today -> auto-close!
    ok_rec = {"completed_date_jst": "2026-11-26", "status": "ok", "sent_count": 12}
    ok_ml = {"date_jst": "2026-11-26", "status": "succeeded", "recommendation_succeeded": True, "failed_steps": []}
    recovered = sahi.enrich_instruction_with_delivery_health(
        {**base_instruction, "generated_at": "2026-11-26 00:00:00"},
        rec_heartbeat=ok_rec,
        ml_status=ok_ml,
        now_jst=now_jst,
    )
    res2 = sahi.sync_instruction_to_issues(recovered, gh)
    assert res2["closed_resolved"], "Expected missed bargain recommendation Issue to auto-close after delivery succeeds"


def test_sync_auto_heal_issues_skips_alert_while_ml_pipeline_legitimately_running():
    from scripts.ops import sync_auto_heal_issues as sahi

    now_jst = datetime.datetime(2026, 11, 26, 7, 15, 0, tzinfo=JST)
    started_utc = (now_jst - datetime.timedelta(minutes=90)).astimezone(datetime.UTC).isoformat()
    running_ml = {
        "date_jst": "2026-11-26",
        "status": "running",
        "started_at_utc": started_utc,
        "recommendation_succeeded": False,
        "failed_steps": [],
    }
    enriched = sahi.enrich_instruction_with_delivery_health(
        {"generated_at": "2026-11-25 21:18:50", "failed_pipeline_steps": [], "targets": []},
        rec_heartbeat={"completed_date_jst": "2026-11-25", "status": "ok"},
        ml_status=running_ml,
        now_jst=now_jst,
    )
    groups = sahi.group_instruction_targets(enriched)
    assert sahi.BARGAIN_NOT_DELIVERED_KEY not in groups


def test_sync_auto_heal_workflow_runs_after_ml_pipeline_window():
    wf = (REPO_ROOT / ".github" / "workflows" / "sync-auto-heal-issues.yml").read_text(encoding="utf-8")
    assert "15 22 * * *" in wf
    assert "20 23 * * *" in wf
