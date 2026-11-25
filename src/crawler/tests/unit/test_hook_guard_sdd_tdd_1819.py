import importlib.util
from pathlib import Path
from unittest.mock import patch


def _load_hook_guard():
    guard_path = Path(__file__).resolve().parents[4] / ".agents" / "scripts" / "hook_guard.py"
    spec = importlib.util.spec_from_file_location("hook_guard", guard_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hook_guard_blocks_tdd_violation_on_pr_create(monkeypatch):
    mod = _load_hook_guard()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    def fake_check_output(cmd, **kwargs):
        if cmd[:2] == ["gh", "pr"]:
            return "0"
        if cmd[:2] == ["git", "diff"]:
            return "src/crawler/package/parser/athomeParser.py\ndocs/2_crawlers/sites/site_structure_athome.md\n"
        return "- [x] Done\n"

    with patch.object(mod.subprocess, "check_output", side_effect=fake_check_output):
        res = mod._check_issue_pr_and_push_guard(
            'gh pr create --title "[#1819] feat: test" --body "Closes #1819"'
        )
    assert res is not None
    assert res["decision"] == "deny"
    assert "TDD" in res["reason"]


def test_hook_guard_blocks_missing_acceptance_criteria_on_pr_create(monkeypatch):
    mod = _load_hook_guard()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    def fake_check_output(cmd, **kwargs):
        if cmd[:2] == ["gh", "pr"]:
            return "0"
        if cmd[:2] == ["git", "diff"]:
            return "src/crawler/package/parser/athomeParser.py\nsrc/crawler/tests/unit/test_x.py\ndocs/2_crawlers/sites/site_structure_athome.md\n"
        if cmd[:2] == ["gh", "issue"]:
            return "No checkboxes here"
        return ""

    with patch.object(mod.subprocess, "check_output", side_effect=fake_check_output):
        res = mod._check_issue_pr_and_push_guard(
            'gh pr create --title "[#1819] feat: test" --body "Closes #1819"'
        )
    assert res is not None
    assert res["decision"] == "deny"
    assert "Acceptance Criteria" in res["reason"]
