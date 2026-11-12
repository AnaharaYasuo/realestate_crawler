"""Issue #1395: Issue未紐付けPRの作成・プッシュ・マージ制限 3層ゲート検証テスト"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK_GUARD_PATH = REPO_ROOT / ".agents" / "scripts" / "hook_guard.py"
ISSUE_GATE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "issue-gate.yml"


def _load_hook_guard():
    spec = importlib.util.spec_from_file_location("hook_guard_mod", HOOK_GUARD_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hook_guard_blocks_pr_create_without_closing_issue():
    """master 向け gh pr create で Closes/Fixes/Resolves #<番号> がない場合は deny されること"""
    mod = _load_hook_guard()

    denied = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": 'gh pr create --base master --head feat/no-issue --title "feat: test" --body "summary only"'
                },
            }
        }
    )
    assert denied["decision"] == "deny"
    assert "Issue" in denied["reason"]


def test_hook_guard_allows_pr_create_with_closes_issue_and_release_pr():
    """Closes #<番号> 付きPR作成および production 向けリリースPR作成は allow されること"""
    mod = _load_hook_guard()

    allowed_feature = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": 'gh pr create --base master --head feat/1395-gate --title "ci: gate (#1395)" --body "Closes #1395"'
                },
            }
        }
    )
    assert allowed_feature["decision"] == "allow"

    allowed_release = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": 'gh pr create --base production --head master --title "release: sync" --body "Release to production"'
                },
            }
        }
    )
    assert allowed_release["decision"] == "allow"


def test_hook_guard_blocks_git_push_branch_without_issue_number():
    """Issue番号を含まない作業ブランチの git push は deny され、Issue番号入りブランチや削除は allow されること"""
    mod = _load_hook_guard()

    denied_push = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git push -u origin feat/no-issue-branch"},
            }
        }
    )
    assert denied_push["decision"] == "deny"

    allowed_push = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git push -u origin feat/1395-strict-issue-pr-gate"},
            }
        }
    )
    assert allowed_push["decision"] == "allow"

    allowed_delete = mod.evaluate_tool_call(
        {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git push origin --delete feat/old-branch"},
            }
        }
    )
    assert allowed_delete["decision"] == "allow"


def test_issue_gate_workflow_enforces_open_issue_closing_keyword_and_unchecked_criteria():
    """issue-gate.yml が PR本文の Closes/Fixes/Resolves 必須化・OPEN状態検証・自動クローズ・未完了チェックボックス検出を備えること"""
    content = ISSUE_GATE_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "issue.data.state !== 'open'" in content
    assert "unchecked.push(item)" in content
    assert "state: 'closed'" in content
    assert "close[sd]?|fixe?[sd]?|resolve[sd]?" in content
