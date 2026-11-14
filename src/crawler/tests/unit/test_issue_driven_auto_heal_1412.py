"""Unit tests for Issue #1412: GitHub Issue-Driven Auto-Heal & Antigravity Scheduled Automation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import yaml

from package.utils.ci_governance_gate import _extract_checkboxes, _strip_fenced_code_blocks


class FakeGhClient:
    """In-memory fake GitHub CLI adapter for deterministic unit testing."""

    def __init__(self, issues: list[dict] | None = None, open_prs: list[dict] | None = None):
        self.issues: dict[int, dict] = {iss["number"]: dict(iss) for iss in (issues or [])}
        self.open_prs: list[dict] = list(open_prs or [])
        self.created_issues: list[dict] = []
        self.comments: list[tuple[int, str]] = []
        self.closed_issues: list[tuple[int, str]] = []
        self.ensured_labels: list[str] = []
        self._next_num = max(self.issues.keys(), default=1400) + 1

    def ensure_labels(self) -> None:
        self.ensured_labels.extend(["auto-heal", "auto-heal:needs-human"])

    def list_open_auto_heal_issues(self) -> list[dict]:
        return [
            iss
            for iss in self.issues.values()
            if iss.get("state", "OPEN").upper() == "OPEN"
            and any(lbl in ("auto-heal", "auto-heal:needs-human") for lbl in iss.get("labels", []))
        ]

    def list_open_prs(self) -> list[dict]:
        return list(self.open_prs)

    def get_issue(self, number: int) -> dict:
        return dict(self.issues[number])

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        num = self._next_num
        self._next_num += 1
        rec = {
            "number": num,
            "title": title,
            "body": body,
            "state": "OPEN",
            "labels": list(labels),
            "comments": [],
        }
        self.issues[num] = rec
        self.created_issues.append(rec)
        return num

    def update_issue_body(self, number: int, body: str) -> None:
        self.issues[number]["body"] = body

    def comment_issue(self, number: int, body: str) -> None:
        self.comments.append((number, body))
        self.issues[number].setdefault("comments", []).append({"body": body})

    def update_labels(self, number: int, add_labels: list[str], remove_labels: list[str]) -> None:
        cur = set(self.issues[number].get("labels", []))
        for rm in remove_labels:
            cur.discard(rm)
        for ad in add_labels:
            cur.add(ad)
        self.issues[number]["labels"] = sorted(cur)

    def close_issue(self, number: int, comment: str) -> None:
        self.issues[number]["state"] = "CLOSED"
        self.closed_issues.append((number, comment))


def test_scan_anomalies_zero_targets_uploads_clean_instruction_to_gcs(tmp_path: Path):
    from scripts.debug_tools import auto_heal_parsers

    temp_dir = tmp_path / "Temp"
    temp_dir.mkdir(parents=True)
    stale_inst = temp_dir / "auto_heal_instruction.json"
    stale_inst.write_text('{"total_anomalies_detected": 5}', encoding="utf-8")

    empty_qs = MagicMock()
    empty_qs.exists.return_value = False
    empty_qs.__iter__.return_value = iter([])

    with (
        patch.object(auto_heal_parsers, "get_project_root", return_value=str(tmp_path)),
        patch.object(auto_heal_parsers, "fetch_slack_error_targets", return_value=[]),
        patch.object(auto_heal_parsers.PropertyEvaluation.objects, "filter", return_value=empty_qs),
        patch.object(auto_heal_parsers, "upload_instruction_to_gcs", return_value=True) as mock_upload,
    ):
        auto_heal_parsers.scan_anomalies_and_generate_instructions(failed_steps=None)

    assert not stale_inst.exists()
    mock_upload.assert_called_once()
    uploaded = mock_upload.call_args[0][0]
    assert uploaded["total_anomalies_detected"] == 0
    assert uploaded["targets"] == []
    assert uploaded["failed_pipeline_steps"] == []
    assert "generated_at" in uploaded


def test_build_target_excludes_source_data_invalid():
    from scripts.debug_tools import auto_heal_parsers

    ev_status = SimpleNamespace(
        company="mitsui",
        property_type="mansion",
        property_id=0,
        property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F01/",
        data_quality_issue="専有面積が0㎡です",
        heal_status="source_data_invalid",
        needs_parser_fix=False,
    )
    ev_reason = SimpleNamespace(
        company="mitsui",
        property_type="mansion",
        property_id=0,
        property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F02/",
        data_quality_issue="[source_data_invalid] 3世代連続失敗",
        heal_status="detected",
        needs_parser_fix=False,
    )

    assert auto_heal_parsers._build_target_from_eval_anomaly(ev_status) is None
    assert auto_heal_parsers._build_target_from_eval_anomaly(ev_reason) is None


def test_scan_anomalies_action_required_mandates_production_merge_and_deploy(tmp_path: Path):
    from scripts.debug_tools import auto_heal_parsers

    empty_qs = MagicMock()
    empty_qs.exists.return_value = False
    empty_qs.__iter__.return_value = iter([])

    sample_target = {
        "url": "https://example.com/p1",
        "company": "mitsui",
        "property_type": "mansion",
        "reason": "価格が0円",
    }

    with (
        patch.object(auto_heal_parsers, "get_project_root", return_value=str(tmp_path)),
        patch.object(auto_heal_parsers, "fetch_slack_error_targets", return_value=[sample_target]),
        patch.object(auto_heal_parsers.PropertyEvaluation.objects, "filter", return_value=empty_qs),
        patch.object(auto_heal_parsers, "summarize_errors_with_gemini", return_value="summary"),
        patch.object(auto_heal_parsers, "upload_instruction_to_gcs", return_value=True) as mock_upload,
        patch.object(auto_heal_parsers, "notify_auto_heal_request"),
    ):
        auto_heal_parsers.scan_anomalies_and_generate_instructions(failed_steps=None)

    uploaded = mock_upload.call_args[0][0]
    assert "production" in uploaded["action_required"]
    assert "Deploy Production" in uploaded["action_required"]


def test_group_instruction_targets_and_build_compliant_issue_body():
    from scripts.ops.sync_auto_heal_issues import build_issue_body, group_instruction_targets

    instruction = {
        "generated_at": "2026-11-14 05:25:00",
        "ai_summary": "mitsui mansion price selector changed.",
        "targets": [
            {
                "company": "mitsui",
                "property_type": "mansion",
                "url": "https://example.com/m1",
                "reason": "価格が0円",
                "frequency": 12,
            },
            {
                "company": "mitsui",
                "property_type": "mansion",
                "url": "https://example.com/m2",
                "reason": "専有面積が極小",
                "frequency": 4,
            },
            {
                "company": "sumifu",
                "property_type": "tochi",
                "url": "https://example.com/s1",
                "reason": "[source_data_invalid] 掲載元面積欠損",
                "frequency": 9,
            },
        ],
        "failed_pipeline_steps": ["Step 2: Train ML"],
    }

    groups = group_instruction_targets(instruction)
    assert "mitsui:mansion" in groups
    assert "sumifu:tochi" not in groups
    assert groups["mitsui:mansion"]["total_frequency"] == 16
    assert len(groups["mitsui:mansion"]["sample_urls"]) == 2
    assert any(k.startswith("pipeline:") for k in groups)

    body = build_issue_body("mitsui:mansion", groups["mitsui:mansion"], instruction)
    assert "<!-- auto-heal-key:mitsui:mansion -->" in body
    assert "<!-- auto-heal-attempts:0 -->" in body
    assert "<!-- auto-heal-sync-ts:2026-11-14 05:25:00 -->" in body
    assert "production" in body
    assert "Deploy Production" in body

    checked, unchecked = _extract_checkboxes(_strip_fenced_code_blocks(body))
    assert len(checked) == 0
    assert len(unchecked) >= 4


def test_sync_creates_deduplicates_respects_circuit_breaker_and_closes_resolved():
    from scripts.ops.sync_auto_heal_issues import sync_instruction_to_issues

    existing_issues = [
        {
            "number": 1401,
            "title": "[Auto-Heal] nomura/kodate パーサー不整合・取得異常の自動修復",
            "body": "<!-- auto-heal-key:nomura:kodate -->\n<!-- auto-heal-attempts:1 -->\n<!-- auto-heal-sync-ts:2026-11-13 05:20:00 -->\n- [ ] Task 1",
            "state": "OPEN",
            "labels": ["auto-heal"],
            "comments": [],
        },
        {
            "number": 1402,
            "title": "[Auto-Heal] sumifu/tochi パーサー不整合・取得異常の自動修復",
            "body": "<!-- auto-heal-key:sumifu:tochi -->\n<!-- auto-heal-attempts:2 -->\n- [ ] Task 1",
            "state": "OPEN",
            "labels": ["auto-heal:needs-human"],
            "comments": [],
        },
        {
            "number": 1403,
            "title": "[Auto-Heal] tokyu/apartment パーサー不整合・取得異常の自動修復",
            "body": "<!-- auto-heal-key:tokyu:apartment -->\n<!-- auto-heal-attempts:0 -->\n- [ ] Task 1",
            "state": "OPEN",
            "labels": ["auto-heal"],
            "comments": [],
        },
        {
            "number": 1404,
            "title": "[Auto-Heal] odakyu/mansion パーサー不整合・取得異常の自動修復",
            "body": "<!-- auto-heal-key:odakyu:mansion -->\n<!-- auto-heal-attempts:1 -->\n- [ ] Task 1",
            "state": "OPEN",
            "labels": ["auto-heal"],
            "comments": [],
        },
    ]
    open_prs = [
        {
            "number": 1500,
            "title": "[#1404] fix(odakyu): update mansion selector",
            "body": "Closes #1404",
            "headRefName": "fix/1404-auto-heal-odakyu-mansion",
        }
    ]
    gh = FakeGhClient(issues=existing_issues, open_prs=open_prs)

    instruction = {
        "generated_at": "2026-11-14 05:25:00",
        "ai_summary": "Summary text",
        "targets": [
            {
                "company": "mitsui",
                "property_type": "mansion",
                "url": "https://example.com/m1",
                "reason": "価格が0円",
                "frequency": 5,
            },
            {
                "company": "nomura",
                "property_type": "kodate",
                "url": "https://example.com/n1",
                "reason": "土地面積が0㎡",
                "frequency": 3,
            },
            {
                "company": "sumifu",
                "property_type": "tochi",
                "url": "https://example.com/s1",
                "reason": "所在地欠損",
                "frequency": 2,
            },
        ],
        "failed_pipeline_steps": [],
    }

    summary = sync_instruction_to_issues(instruction, gh, dry_run=False)
    assert len(summary["created"]) == 1
    assert summary["updated"] == [1401]
    assert summary["skipped_needs_human"] == [1402]
    assert summary["closed_resolved"] == [1403]
    # Issue #1404 has an open PR #1500, so it MUST NOT be prematurely auto-closed!
    assert gh.issues[1404]["state"] == "OPEN"
    assert "auto-heal" not in gh.issues[1402]["labels"]

    # Re-running with the exact same generated_at must be idempotent (0 new comments/issues)
    summary_repeat = sync_instruction_to_issues(instruction, gh, dry_run=False)
    assert summary_repeat["created"] == []
    assert summary_repeat["updated"] == []


def test_list_actionable_record_attempt_circuit_breaker_and_mark_criteria_done():
    from scripts.ops.sync_auto_heal_issues import (
        list_actionable_issues,
        mark_issue_criteria_done,
        record_heal_attempt,
    )

    body_1410 = (
        "<!-- auto-heal-key:mitsui:mansion -->\n"
        "<!-- auto-heal-attempts:0 -->\n"
        "## 受入基準\n"
        "- [ ] SDD更新\n"
        "- [ ] TDD追加\n"
        "```markdown\n"
        "- [ ] コードブロック内は変更しない\n"
        "```\n"
    )
    gh = FakeGhClient(
        issues=[
            {
                "number": 1410,
                "title": "[Auto-Heal] mitsui/mansion",
                "body": body_1410,
                "state": "OPEN",
                "labels": ["auto-heal"],
            },
            {
                "number": 1411,
                "title": "[Auto-Heal] sumifu/mansion",
                "body": "<!-- auto-heal-key:sumifu:mansion -->\n<!-- auto-heal-attempts:0 -->\n- [ ] Task",
                "state": "OPEN",
                "labels": ["auto-heal"],
            },
            {
                "number": 1412,
                "title": "[Auto-Heal] tokyu/mansion",
                "body": "<!-- auto-heal-key:tokyu:mansion -->\n<!-- auto-heal-attempts:2 -->\n- [ ] Task",
                "state": "OPEN",
                "labels": ["auto-heal:needs-human"],
            },
        ],
        open_prs=[
            {
                "number": 1501,
                "title": "[#1411] fix(sumifu): parser",
                "body": "Closes #1411",
                "headRefName": "fix/1411-auto-heal",
            }
        ],
    )

    actionable = list_actionable_issues(gh)
    assert actionable["count"] == 1
    assert actionable["issues"][0]["number"] == 1410

    r1 = record_heal_attempt(1410, gh, max_attempts=2)
    assert r1 == {"issue_number": 1410, "attempts": 1, "escalated": False}

    r2 = record_heal_attempt(1410, gh, max_attempts=2)
    assert r2 == {"issue_number": 1410, "attempts": 2, "escalated": False}

    # 3rd attempt exceeds max_attempts=2 -> circuit breaker trips!
    r3 = record_heal_attempt(1410, gh, max_attempts=2)
    assert r3 == {"issue_number": 1410, "attempts": 3, "escalated": True}
    assert "auto-heal:needs-human" in gh.issues[1410]["labels"]
    assert "auto-heal" not in gh.issues[1410]["labels"]

    # Check off criteria on #1411
    mark_issue_criteria_done(1410, gh)
    updated_body = gh.issues[1410]["body"]
    checked, unchecked = _extract_checkboxes(_strip_fenced_code_blocks(updated_body))
    assert len(checked) == 2
    assert len(unchecked) == 0
    assert "- [ ] コードブロック内は変更しない" in updated_body


def test_sync_auto_heal_issues_workflow_yaml_structure():
    repo_root = Path(__file__).resolve().parents[4]
    wf_path = repo_root / ".github" / "workflows" / "sync-auto-heal-issues.yml"
    assert wf_path.exists(), f"Missing workflow file: {wf_path}"

    parsed = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    triggers = parsed.get("on") or parsed.get(True)
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert any(item.get("cron") == "15 21 * * *" for item in triggers["schedule"])

    perms = parsed.get("permissions", {})
    assert perms.get("issues") == "write"
    assert perms.get("id-token") == "write"
    assert perms.get("contents") == "read"

    raw_text = wf_path.read_text(encoding="utf-8")
    assert "sync_auto_heal_issues.py" in raw_text
    assert "--pull-from-gcs" in raw_text
    assert (
        json.dumps({"ok": True})  # sanity keep json import used
        and "GCP_WORKLOAD_IDENTITY_PROVIDER" in raw_text
    )


def test_subprocess_gh_client_and_cli_entrypoints(tmp_path: Path, capsys):
    from scripts.ops import sync_auto_heal_issues
    from scripts.ops.sync_auto_heal_issues import SubprocessGhClient

    responses = [
        SimpleNamespace(stdout=""),  # label create auto-heal
        SimpleNamespace(stdout=""),  # label create needs-human
        SimpleNamespace(
            stdout=json.dumps(
                [
                    {
                        "number": 1450,
                        "title": "[Auto-Heal] mitsui/mansion",
                        "body": "<!-- auto-heal-key:mitsui:mansion -->\n- [ ] Task",
                        "state": "OPEN",
                        "labels": [{"name": "auto-heal"}],
                        "comments": [],
                    }
                ]
            )
        ),
        SimpleNamespace(stdout=json.dumps([{"number": 1500, "title": "PR", "body": "", "headRefName": "feat/1"}])),
        SimpleNamespace(
            stdout=json.dumps(
                {
                    "number": 1450,
                    "title": "[Auto-Heal] mitsui/mansion",
                    "body": "<!-- auto-heal-key:mitsui:mansion -->\n- [ ] Task",
                    "state": "OPEN",
                    "labels": ["auto-heal"],
                    "comments": [],
                }
            )
        ),
        SimpleNamespace(stdout="https://github.com/owner/repo/issues/1451\n"),
        SimpleNamespace(stdout=""),  # update_issue_body
        SimpleNamespace(stdout=""),  # comment_issue
        SimpleNamespace(stdout=""),  # update_labels
        SimpleNamespace(stdout=""),  # close_issue -> comment
        SimpleNamespace(stdout=""),  # close_issue -> close
    ]

    with patch("subprocess.run", side_effect=responses) as mock_run:
        client = SubprocessGhClient()
        client.ensure_labels()
        issues = client.list_open_auto_heal_issues()
        assert len(issues) == 1 and issues[0]["labels"] == ["auto-heal"]
        prs = client.list_open_prs()
        assert len(prs) == 1
        got = client.get_issue(1450)
        assert got["number"] == 1450
        created_num = client.create_issue("Title", "Body", ["auto-heal"])
        assert created_num == 1451
        client.update_issue_body(1451, "Updated")
        client.comment_issue(1451, "Comment")
        client.update_labels(1451, ["auto-heal:needs-human"], ["auto-heal"])
        client.close_issue(1451, "Closing")
        assert mock_run.call_count == len(responses)

    # Dry-run sync via CLI --instruction-file
    inst_file = tmp_path / "inst.json"
    inst_file.write_text(
        json.dumps(
            {
                "generated_at": "2026-11-14 06:00:00",
                "targets": [
                    {
                        "company": "mitsui",
                        "property_type": "mansion",
                        "url": "https://example.com/1",
                        "reason": "価格0円",
                        "frequency": 2,
                    }
                ],
                "failed_pipeline_steps": [],
            }
        ),
        encoding="utf-8",
    )

    fake_gh = FakeGhClient(
        issues=[
            {
                "number": 1460,
                "title": "[Auto-Heal] stale/tochi",
                "body": "<!-- auto-heal-key:stale:tochi -->\n- [ ] Task",
                "state": "OPEN",
                "labels": ["auto-heal"],
                "comments": [],
            }
        ]
    )
    with patch.object(sync_auto_heal_issues, "SubprocessGhClient", return_value=fake_gh):
        assert sync_auto_heal_issues.main(["--instruction-file", str(inst_file), "--dry-run"]) == 0
        assert fake_gh.created_issues == []
        assert sync_auto_heal_issues.main(["--instruction-file", str(inst_file)]) == 0
        assert len(fake_gh.created_issues) == 1
        new_num = fake_gh.created_issues[0]["number"]
        assert sync_auto_heal_issues.main(["--list-actionable"]) == 0
        assert sync_auto_heal_issues.main(["--record-attempt", str(new_num)]) == 0
        assert sync_auto_heal_issues.main(["--mark-criteria-done", str(new_num)]) == 0
        assert sync_auto_heal_issues.main(["--escalate", str(new_num), "--reason", "manual check"]) == 0
        assert sync_auto_heal_issues.main(["--instruction-file", str(tmp_path / "missing.json")]) == 0

    out = capsys.readouterr().out
    assert '"escalated": true' in out


def test_pull_instruction_from_gcs_direct():
    from scripts.ops import sync_auto_heal_issues

    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_text.return_value = '{"generated_at": "2026-11-14 05:30:00", "targets": []}'
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", return_value=mock_client):
        data = sync_auto_heal_issues.pull_instruction_from_gcs_direct("test-bucket", "auto_heal/latest_instruction.json")
        assert data == {"generated_at": "2026-11-14 05:30:00", "targets": []}

    mock_blob.exists.return_value = False
    with patch("google.cloud.storage.Client", return_value=mock_client):
        assert sync_auto_heal_issues.pull_instruction_from_gcs_direct("test-bucket", "missing.json") is None

