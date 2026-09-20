"""Review Conversation Gateワークフローの静的契約テスト。"""
import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "review-gate.yml"


@pytest.fixture(scope="module")
def review_gate():
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.load(workflow_file, Loader=yaml.BaseLoader)


@pytest.fixture(scope="module")
def gate_script(review_gate):
    return review_gate["jobs"]["verify-conversations-resolved"]["steps"][0]["with"]["script"]


def test_review_gate_subscribes_to_every_mutating_review_event(review_gate):
    """レビュー状態やチェック欄を変え得る全イベントでゲートが再評価されること"""
    triggers = review_gate["on"]

    assert set(triggers["pull_request_review"]["types"]) == {
        "submitted",
        "edited",
        "dismissed",
    }
    assert set(triggers["pull_request_review_comment"]["types"]) == {
        "created",
        "edited",
        "deleted",
    }
    assert set(triggers["issue_comment"]["types"]) == {
        "created",
        "edited",
        "deleted",
    }


@pytest.mark.parametrize(
    ("line", "should_match"),
    [
        ("- [ ] unfinished", True),
        ("  * [ ] another item", True),
        ("\t- [ ]tab-indented", True),
        ("- [x] completed", False),
        ("1. [ ] numbered item", False),
        ("text - [ ] inline checkbox", False),
    ],
)
def test_review_gate_unchecked_checkbox_pattern(gate_script, line, should_match):
    """ワークフロー内の実際の正規表現が対象の未完了項目だけを検出すること"""
    match = re.search(r"line\.match\(/(.+?)/\);", gate_script)
    assert match, "The workflow's unchecked-checkbox regular expression was not found"
    checkbox_pattern = re.compile(match.group(1))

    assert bool(checkbox_pattern.match(line)) is should_match


def test_review_gate_scans_all_pr_text_sources_and_review_states(gate_script):
    """PR本文、レビュー、通常コメント、インラインコメントと変更要求を集約すること"""
    required_calls = {
        "github.rest.pulls.listReviews",
        "github.rest.issues.listComments",
        "github.rest.pulls.listReviewComments",
        "reviewThreads(first: 100, after: $cursor)",
        "r.state === 'CHANGES_REQUESTED'",
        "github.rest.repos.getCombinedStatusForRef",
        "github.rest.checks.listForRef",
    }

    assert all(call in gate_script for call in required_calls)
    assert "radioGroupId" in gate_script
    assert "Fix all pre-merge checks with AI" in gate_script


def test_review_gate_has_permissions_to_publish_head_check(review_gate, gate_script):
    """判定結果をPRのHEAD SHAへ同期する権限と処理が定義されていること"""
    permissions = review_gate["permissions"]

    assert permissions["checks"] == "write"
    assert permissions["statuses"] == "read"
    assert "github.rest.checks.create" in gate_script
    assert "head_sha: headSha" in gate_script
