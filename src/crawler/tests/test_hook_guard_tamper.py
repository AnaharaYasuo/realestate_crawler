import importlib.util
from pathlib import Path


def _load_hook_guard():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / ".agents" / "scripts" / "hook_guard.py"
    spec = importlib.util.spec_from_file_location("hook_guard", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_allows_normal_test_edit_in_worktree():
    hg = _load_hook_guard()
    payload = {
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": "c:/repo/.worktrees/feat-1585/src/crawler/tests/test_sample.py",
                "Target": "assert result == 1",
                "Replacement": "assert result == 2",
            },
        }
    }
    assert hg.evaluate_tool_call(payload)["decision"] == "allow"


def test_denies_adding_pytest_skip_to_test_file():
    hg = _load_hook_guard()
    payload = {
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": "c:/repo/.worktrees/feat-1585/src/crawler/tests/test_sample.py",
                "Target": "def test_something():",
                "Replacement": "@pytest.mark.skip(reason='flaky')\ndef test_something():",
            },
        }
    }
    res = hg.evaluate_tool_call(payload)
    assert res["decision"] == "deny"
    assert "tamper" in res["reason"].lower() or "skip" in res["reason"].lower()


def test_denies_commenting_out_assertion_in_test_file():
    hg = _load_hook_guard()
    payload = {
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": "c:/repo/.worktrees/feat-1585/src/crawler/tests/test_sample.py",
                "Target": "    assert price == 1000",
                "Replacement": "    # assert price == 1000",
            },
        }
    }
    res = hg.evaluate_tool_call(payload)
    assert res["decision"] == "deny"


def test_denies_trivial_assert_true_replacement():
    hg = _load_hook_guard()
    payload = {
        "toolCall": {
            "name": "edit_file",
            "args": {
                "Path": "c:/repo/.worktrees/feat-1585/src/crawler/tests/test_sample.py",
                "Target": "    assert price == 1000",
                "Replacement": "    assert True",
            },
        }
    }
    res = hg.evaluate_tool_call(payload)
    assert res["decision"] == "deny"
