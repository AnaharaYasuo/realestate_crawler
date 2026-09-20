"""Review Conversation Gate ワークフローの構成契約テスト。"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "review-gate.yml"


def _load_workflow():
    # BaseLoader avoids YAML 1.1 treating the GitHub Actions `on` key as boolean.
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.load(workflow_file, Loader=yaml.BaseLoader)


def _workflow_script() -> str:
    workflow = _load_workflow()
    return workflow["jobs"]["verify-conversations-resolved"]["steps"][0]["with"]["script"]


def test_review_gate_rechecks_every_mutating_review_event():
    """編集・削除・dismissを含む全イベントで古い判定が残らないこと。"""
    workflow = _load_workflow()
    events = workflow["on"]

    assert events["pull_request"]["types"] == ["opened", "edited", "synchronize", "reopened"]
    assert events["pull_request"]["branches"] == ["master", "production"]
    assert events["pull_request_review"]["types"] == ["submitted", "edited", "dismissed"]
    assert events["pull_request_review_comment"]["types"] == ["created", "edited", "deleted"]
    assert events["issue_comment"]["types"] == ["created", "edited", "deleted"]


def test_review_gate_declares_permissions_needed_by_its_api_calls():
    workflow = _load_workflow()

    assert workflow["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "issues": "read",
        "checks": "write",
        "statuses": "read",
    }


def test_review_gate_scans_every_checkbox_source_with_pagination():
    """PR本文と全コメント種別を走査し、複数ページでも見落とさないこと。"""
    script = _workflow_script()

    assert "extractUnchecked(pr.body, 'PR 本文 (Description)')" in script
    for endpoint in (
        "github.rest.pulls.listReviews",
        "github.rest.issues.listComments",
        "github.rest.pulls.listReviewComments",
    ):
        assert f"github.paginate({endpoint}" in script

    assert "extractUnchecked(r.body, `Review by @${author} (ID: ${r.id})`)" in script
    assert "extractUnchecked(c.body, `Comment by @${author} (ID: ${c.id})`)" in script
    assert "extractUnchecked(rc.body, `Inline comment by @${author}" in script
    assert "trimmed.match(/^[-*]\\s*\\[([ ])\\]\\s*(.*)$/)" in script
    assert "content.replace(/<!--.*?-->/g, '').trim()" in script


def test_review_gate_paginates_checks_and_review_threads_safely():
    """CodeRabbit checksとGraphQLスレッドを全件取得し、停止カーソルを検出すること。"""
    script = _workflow_script()

    assert "github.paginate(github.rest.checks.listForRef" in script
    assert "per_page: 100" in script
    assert "reviewThreads(first: 100, after: $cursor)" in script
    assert "if (hasMorePages && (!nextCursor || nextCursor === cursor))" in script
    assert "GraphQL reviewThreads pagination did not advance" in script


def test_review_gate_blocks_pending_checks_and_latest_changes_requested_review():
    """進行中CodeRabbitと各レビュアーの最新CHANGES_REQUESTEDを失敗扱いすること。"""
    script = _workflow_script()

    assert "s.context.toLowerCase().includes('coderabbit')" in script
    assert "s.state === 'pending'" in script
    assert "c.status !== 'completed'" in script
    assert "latestReviewByUser.set(r.user.login, r)" in script
    assert "r.state !== 'COMMENTED' && r.state !== 'DISMISSED'" in script
    assert "r.state === 'CHANGES_REQUESTED'" in script


def test_review_gate_syncs_aggregate_result_to_pr_head_sha():
    """全ゲート結果をPRのHEAD SHAに紐づくcheck runへ同期すること。"""
    script = _workflow_script()

    assert "const headSha = pr.head && pr.head.sha" in script
    assert "await github.rest.checks.create" in script
    assert "head_sha: headSha" in script
    assert "conclusion: hasFailure ? 'failure' : 'success'" in script
    assert "core.setFailed(`PR #${prNumber} cannot be merged:" in script
    assert "Review Conversations & Checkboxes Check Passed" in script
