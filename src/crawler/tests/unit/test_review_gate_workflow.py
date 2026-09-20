"""Contract tests for the review conversation gate workflow."""

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "review-gate.yml"


def _load_workflow():
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.safe_load(workflow_file)


def _workflow_events(workflow):
    # PyYAML 1.1 treats the unquoted GitHub Actions key ``on`` as boolean true.
    return workflow.get("on") or workflow.get(True)


def _gate_script(workflow=None):
    workflow = workflow or _load_workflow()
    steps = workflow["jobs"]["verify-conversations-resolved"]["steps"]
    github_script_step = next(step for step in steps if step.get("uses") == "actions/github-script@v7")
    return github_script_step["with"]["script"]


def test_review_gate_retriggers_for_every_mutable_review_source():
    """Edits and deletions must rerun the gate so stale failures can be cleared."""
    events = _workflow_events(_load_workflow())

    assert events["pull_request"]["branches"] == ["master", "production"]
    assert set(events["pull_request"]["types"]) >= {"opened", "edited", "synchronize", "reopened"}
    assert set(events["pull_request_review"]["types"]) == {"submitted", "edited", "dismissed"}
    assert set(events["pull_request_review_comment"]["types"]) == {"created", "edited", "deleted"}
    assert set(events["issue_comment"]["types"]) == {"created", "edited", "deleted"}


def test_review_gate_has_only_the_permissions_needed_by_its_api_calls():
    workflow = _load_workflow()

    assert workflow["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "issues": "read",
        "checks": "write",
        "statuses": "read",
    }


def test_issue_comment_events_resolve_the_pull_request_before_evaluation():
    script = _gate_script()

    assert "context.payload.issue.pull_request" in script
    assert "github.rest.pulls.get" in script
    assert "pull_number: context.payload.issue.number" in script
    assert "Failed to fetch pull request for issue" in script
    assert "targetBranch !== 'master' && targetBranch !== 'production'" in script


def test_coderabbit_pending_detection_uses_the_current_pr_head_and_all_check_pages():
    script = _gate_script()

    assert "const headSha = pr.head && pr.head.sha" in script
    assert "github.rest.repos.getCombinedStatusForRef" in script
    assert "const pendingStatus = crStatuses.find(s => s.state === 'pending')" in script
    assert "github.paginate(github.rest.checks.listForRef" in script
    assert "const inProgressCheck = crChecks.find(c => c.status !== 'completed')" in script
    assert script.count("ref: headSha") == 2


@pytest.mark.parametrize(
    ("line", "expected_text"),
    [
        ("- [ ] implement retry", "implement retry"),
        ("  * [ ] nested item  ", "nested item"),
        ("-    [ ]spacing is optional", "spacing is optional"),
        ("- [ ] task <!-- internal marker -->", "task"),
    ],
)
def test_unchecked_checkbox_pattern_accepts_supported_markdown(line, expected_text):
    script = _gate_script()
    assert "trimmed.match(/^[-*]\\s*\\[([ ])\\]\\s*(.*)$/)" in script

    match = re.match(r"^[-*]\s*\[([ ])\]\s*(.*)$", line.strip())
    assert match is not None
    assert re.sub(r"<!--.*?-->", "", match.group(2)).strip() == expected_text


@pytest.mark.parametrize(
    "line",
    [
        "- [x] completed",
        "* [X] completed",
        "+ [ ] unsupported bullet",
        "plain [ ] text",
        "- [] malformed",
    ],
)
def test_unchecked_checkbox_pattern_rejects_non_pending_items(line):
    assert re.match(r"^[-*]\s*\[([ ])\]\s*(.*)$", line.strip()) is None


def test_all_pr_text_surfaces_are_paginated_and_scanned_for_checkboxes():
    script = _gate_script()

    assert "extractUnchecked(pr.body, 'PR 本文 (Description)')" in script
    assert "github.paginate(github.rest.pulls.listReviews" in script
    assert "extractUnchecked(r.body, `Review by @${author} (ID: ${r.id})`)" in script
    assert "github.paginate(github.rest.issues.listComments" in script
    assert "extractUnchecked(c.body, `Comment by @${author} (ID: ${c.id})`)" in script
    assert "github.paginate(github.rest.pulls.listReviewComments" in script
    assert "extractUnchecked(rc.body, `Inline comment by @${author}" in script


def test_review_thread_pagination_fails_closed_if_the_cursor_stalls():
    script = _gate_script()

    assert "reviewThreads(first: 100, after: $cursor)" in script
    assert "allThreads.push(...connection.nodes)" in script
    assert "hasMorePages && (!nextCursor || nextCursor === cursor)" in script
    assert "GitHub GraphQL reviewThreads pagination did not advance." in script
    assert "Failed to fetch review threads via GraphQL" in script


def test_latest_non_dismissed_review_controls_changes_requested_state():
    script = _gate_script()

    assert "const latestReviewByUser = new Map()" in script
    assert "r.state !== 'COMMENTED' && r.state !== 'DISMISSED'" in script
    assert "latestReviewByUser.set(r.user.login, r)" in script
    assert "r.state === 'CHANGES_REQUESTED'" in script


def test_gate_writes_a_terminal_check_to_the_pr_head_for_pass_and_failure():
    script = _gate_script()

    assert "await github.rest.checks.create" in script
    assert "head_sha: headSha" in script
    assert "status: 'completed'" in script
    assert "conclusion: hasFailure ? 'failure' : 'success'" in script
    assert "core.setFailed(`PR #${prNumber} cannot be merged:" in script
    assert "Review Conversations & Checkboxes Check Passed" in script
