"""TDD Unit Tests for CI Governance 4-Gate Engine (Issue #1395).

Verifies mechanical enforcement of:
  - Gate A: Issue-Driven (Closes #N, [#N] title, branch N token, OPEN non-PR Issue, issue.created_at <= pr.created_at)
  - Gate B: Acceptance Criteria & PR Checklist Completion (total > 0, 0 unchecked in Issue & PR body)
  - Gate C: Spec-Driven / SDD (7-domain docs/[1-7]_*/*.md required when src/terraform/.github/.agents change)
  - Gate D: Test-Driven / TDD (src/crawler/tests/**/*.py required when executable .py or workflow .yml/.yaml change)
"""

import json

import pytest

from package.utils.ci_governance_gate import evaluate_pr_governance, run_stdio


def _valid_payload(**overrides) -> dict:
    base = {
        "repo_owner": "AnaharaYasuo",
        "repo_name": "realestate_crawler",
        "pr": {
            "number": 1396,
            "title": "[#1395] ci(governance): enforce SDD and TDD gates",
            "body": "Summary\n\nCloses #1395\n- [x] Verified locally",
            "head_ref": "feat/1395-strict-issue-pr-gate",
            "user_login": "AnaharaYasuo",
            "created_at": "2026-11-12T11:19:54Z",
        },
        "issue": {
            "exists": True,
            "number": 1395,
            "state": "open",
            "is_pull_request": False,
            "created_at": "2026-11-12T11:16:41Z",
            "body": "## Acceptance Criteria\n- [x] Spec updated\n- [x] Tests passing",
        },
        "files": [
            "docs/6_platform_and_release/pre_pr_check_specification.md",
            "src/crawler/package/utils/ci_governance_gate.py",
            "src/crawler/tests/unit/test_ci_governance_gate.py",
        ],
    }
    for key, val in overrides.items():
        if key in ("pr", "issue") and isinstance(val, dict):
            base[key] = {**base[key], **val}
        else:
            base[key] = val
    return base


def test_dependabot_pr_is_exempt():
    payload = _valid_payload(
        pr={"user_login": "dependabot[bot]", "title": "chore(deps): bump foo", "body": "", "head_ref": "dependabot/pip/foo"},
        issue={"exists": False},
        files=["src/crawler/requirements.txt"],
    )
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is True
    assert verdict["auto_close"] is False
    assert verdict["fail_reason"] == ""


def test_valid_full_sdd_tdd_issue_pr_passes_including_equal_timestamp():
    payload = _valid_payload(
        pr={"created_at": "2026-11-12T11:16:41Z"},
        issue={"created_at": "2026-11-12T11:16:41Z"},
    )
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is True
    assert verdict["auto_close"] is False
    assert verdict["issue_number"] == 1395


def test_docs_only_pr_passes_without_requiring_tests():
    payload = _valid_payload(
        files=["docs/1_architecture/requirements_master.md", "README.md"],
    )
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is True
    assert verdict["auto_close"] is False


def test_missing_closing_keyword_triggers_auto_close():
    payload = _valid_payload(pr={"body": "Related to #1395 without closing keyword"})
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert verdict["auto_close"] is True
    assert "Closes" in verdict["comment_body"]


@pytest.mark.parametrize(
    "bad_title",
    [
        "ci(governance): missing bracket prefix (#1395)",
        "[#9999] ci(governance): mismatched issue number",
        "[#1395]no-space-after-bracket",
    ],
)
def test_invalid_or_mismatched_title_prefix_fails(bad_title: str):
    payload = _valid_payload(pr={"title": bad_title})
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert verdict["auto_close"] is False
    assert "title" in verdict["fail_reason"].lower() or "タイトル" in verdict["comment_body"]


@pytest.mark.parametrize(
    "bad_branch",
    [
        "feat/no-issue-id",
        "feat/9999-wrong-issue",
        "feat/13950-superstring-number",
        "feat/21395-prefix-number",
    ],
)
def test_branch_missing_exact_issue_number_token_fails(bad_branch: str):
    payload = _valid_payload(pr={"head_ref": bad_branch})
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert verdict["auto_close"] is False
    assert "branch" in verdict["fail_reason"].lower()


@pytest.mark.parametrize(
    "issue_override,expected_reason_substr",
    [
        ({"exists": False}, "exist"),
        ({"is_pull_request": True}, "Pull Request"),
        ({"state": "closed"}, "open"),
    ],
)
def test_nonexistent_pr_ref_or_closed_issue_triggers_auto_close(issue_override: dict, expected_reason_substr: str):
    payload = _valid_payload(issue=issue_override)
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert verdict["auto_close"] is True
    assert expected_reason_substr.lower() in verdict["fail_reason"].lower()


def test_retroactive_issue_created_after_pr_fails():
    payload = _valid_payload(
        pr={"created_at": "2026-11-12T12:00:00Z"},
        issue={"created_at": "2026-11-12T12:00:01Z"},
    )
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert verdict["auto_close"] is False
    assert "issue-first" in verdict["fail_reason"].lower() or "created" in verdict["fail_reason"].lower()


def test_issue_zero_or_unchecked_acceptance_criteria_fails():
    no_criteria = _valid_payload(issue={"body": "Plain description with no checkboxes"})
    v1 = evaluate_pr_governance(no_criteria)
    assert v1["passed"] is False
    assert v1["auto_close"] is False
    assert "Acceptance Criteria" in v1["fail_reason"]

    unchecked_criteria = _valid_payload(
        issue={"body": "## Criteria\n- [x] Done item\n* [ ] Pending item"}
    )
    v2 = evaluate_pr_governance(unchecked_criteria)
    assert v2["passed"] is False
    assert v2["auto_close"] is False
    assert "Pending item" in v2["comment_body"]


def test_pr_body_unchecked_checkbox_fails_outside_code_fence_only():
    in_fence = _valid_payload(
        pr={"body": "Closes #1395\n```markdown\n- [ ] example inside code block\n```\n- [x] real item"}
    )
    assert evaluate_pr_governance(in_fence)["passed"] is True

    outside_fence = _valid_payload(
        pr={"body": "Closes #1395\n- [x] done\n- [ ] left unchecked in PR"}
    )
    verdict = evaluate_pr_governance(outside_fence)
    assert verdict["passed"] is False
    assert "PR" in verdict["fail_reason"]


@pytest.mark.parametrize(
    "changed_files",
    [
        ["src/crawler/package/foo.py", "src/crawler/tests/unit/test_foo.py"],
        ["src/crawler/package/foo.py", "docs/AGENTS.md", "src/crawler/tests/unit/test_foo.py"],
        ["terraform/cloud_run.tf"],
        [".github/workflows/issue-gate.yml", "src/crawler/tests/unit/test_ci.py"],
        [".agents/hooks.json"],
    ],
)
def test_sdd_gate_blocks_changes_without_7_domain_spec_update(changed_files: list[str]):
    payload = _valid_payload(files=changed_files)
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert "SDD" in verdict["fail_reason"]


@pytest.mark.parametrize(
    "changed_files",
    [
        ["src/crawler/package/foo.py", "docs/1_architecture/basic_design_master.md"],
        [".agents/scripts/hook_guard.py", "docs/6_platform_and_release/pre_pr_check_specification.md"],
        [".github/workflows/issue-gate.yml", "docs/6_platform_and_release/pre_pr_check_specification.md"],
        [".github/workflows/deploy.yaml", "docs/6_platform_and_release/pre_pr_check_specification.md"],
    ],
)
def test_tdd_gate_blocks_executable_or_workflow_changes_without_tests(changed_files: list[str]):
    payload = _valid_payload(files=changed_files)
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is False
    assert "TDD" in verdict["fail_reason"]


def test_terraform_plus_7_domain_spec_passes_without_requiring_python_test():
    payload = _valid_payload(
        files=["terraform/cloud_run.tf", "docs/6_platform_and_release/pre_pr_check_specification.md"]
    )
    verdict = evaluate_pr_governance(payload)
    assert verdict["passed"] is True


def test_stdio_roundtrip_returns_verdict_json():
    out_raw = run_stdio(json.dumps(_valid_payload()))
    verdict = json.loads(out_raw)
    assert verdict["passed"] is True
    assert verdict["issue_number"] == 1395
