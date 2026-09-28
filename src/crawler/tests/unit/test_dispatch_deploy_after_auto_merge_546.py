"""Issue #546: auto-merge by GITHUB_TOKEN must still trigger exactly one production deploy."""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ops import dispatch_deploy_after_auto_merge as dd

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


class FakeGh:
    """Scripted gh runner: returns queued responses per command prefix and records calls."""

    def __init__(self, views=None, open_prs="[]", dispatch_rc=0):
        self.views = list(views or [])
        self.open_prs = open_prs
        self.dispatch_rc = dispatch_rc
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return 0, self.open_prs
        if args[:2] == ["pr", "view"]:
            item = self.views.pop(0) if len(self.views) > 1 else self.views[0]
            if isinstance(item, Exception):
                raise item
            return 0, json.dumps(item)
        if args[:2] == ["workflow", "run"]:
            return self.dispatch_rc, ""
        raise AssertionError(f"unexpected gh call: {args}")

    @property
    def dispatch_calls(self):
        return [c for c in self.calls if c[:2] == ["workflow", "run"]]


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, sec):
        self.sleeps.append(sec)
        self.now += sec


def _merged(login):
    return {"state": "MERGED", "mergedBy": {"login": login}}


@pytest.mark.parametrize(
    ("state", "login", "expected"),
    [
        ("MERGED", "app/github-actions", dd.DISPATCH),
        ("MERGED", "github-actions", dd.DISPATCH),
        ("MERGED", "AnaharaYasuo", dd.SKIP_HUMAN_MERGE),
        ("MERGED", None, dd.SKIP_HUMAN_MERGE),
        ("CLOSED", None, dd.SKIP_CLOSED),
        ("OPEN", None, dd.WAIT),
    ],
)
def test_decide_action(state, login, expected):
    assert dd.decide_action(state, login) == expected


def test_auto_merge_by_github_actions_dispatches_deploy_once():
    gh = FakeGh(views=[{"state": "OPEN", "mergedBy": None}, _merged("app/github-actions")])
    clock = FakeClock()

    result = dd.wait_and_dispatch("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == dd.DISPATCH
    assert gh.dispatch_calls == [["workflow", "run", "deploy-production.yml", "--ref", "production"]]
    assert clock.sleeps == [30]


def test_human_merge_does_not_dispatch():
    gh = FakeGh(views=[_merged("AnaharaYasuo")])
    clock = FakeClock()

    result = dd.wait_and_dispatch("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == dd.SKIP_HUMAN_MERGE
    assert gh.dispatch_calls == []


def test_closed_without_merge_does_not_dispatch():
    gh = FakeGh(views=[{"state": "CLOSED", "mergedBy": None}])
    clock = FakeClock()

    assert dd.wait_and_dispatch("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time) == dd.SKIP_CLOSED
    assert gh.dispatch_calls == []


def test_timeout_is_finite_and_does_not_dispatch():
    gh = FakeGh(views=[{"state": "OPEN", "mergedBy": None}])
    clock = FakeClock()

    result = dd.wait_and_dispatch("544", 90, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == dd.TIMED_OUT
    assert gh.dispatch_calls == []
    assert sum(clock.sleeps) <= 90


def test_transient_gh_errors_keep_waiting():
    gh = FakeGh(
        views=[
            subprocess.TimeoutExpired(cmd="gh", timeout=10),
            {"state": "OPEN", "mergedBy": None},
            _merged("github-actions"),
        ]
    )
    clock = FakeClock()

    result = dd.wait_and_dispatch("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == dd.DISPATCH
    assert len(gh.dispatch_calls) == 1


def test_dispatch_failure_is_reported():
    gh = FakeGh(views=[_merged("app/github-actions")], dispatch_rc=1)
    clock = FakeClock()

    result = dd.wait_and_dispatch("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == dd.DISPATCH_FAILED


@pytest.mark.parametrize(
    ("open_prs", "expected"),
    [('[{"number": 544}]', "544"), ("[]", None), ("", None)],
)
def test_find_release_pr(open_prs, expected):
    assert dd.find_release_pr(FakeGh(open_prs=open_prs)) == expected


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (dd.DISPATCH, 0),
        (dd.SKIP_HUMAN_MERGE, 0),
        (dd.SKIP_CLOSED, 0),
        (dd.TIMED_OUT, 0),
        (dd.DISPATCH_FAILED, 1),
    ],
)
def test_exit_code(result, code):
    assert dd.exit_code_for(result) == code


def test_main_without_open_release_pr_exits_cleanly():
    gh = FakeGh(open_prs="[]")
    assert dd.main(["--timeout-sec", "60"], run_gh=gh) == 0
    assert gh.dispatch_calls == []


def test_gh_calls_use_finite_timeout(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(dd.subprocess, "run", fake_run)
    assert dd.run_gh(["pr", "list"]) == (0, "[]")
    assert captured["cmd"][0] == "gh"
    assert 0 < captured["timeout"] <= 10


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _on(workflow):
    return workflow.get("on") or workflow.get(True, {})


def test_deploy_production_accepts_dispatch_and_is_serialized():
    workflow = _load("deploy-production.yml")
    on = _on(workflow)
    assert "production" in on["push"]["branches"]
    assert "workflow_dispatch" in on
    assert workflow["concurrency"]["group"] == "deploy-production"
    assert workflow["concurrency"]["cancel-in-progress"] is False


def test_auto_release_pr_has_dispatch_job():
    workflow = _load("auto-release-pr.yml")
    job = workflow["jobs"]["dispatch-deploy-after-auto-merge"]
    assert job["needs"] == "create-or-update-release-pr"
    assert job["permissions"]["actions"] == "write"
    assert job["concurrency"]["group"] == "release-pr-deploy-dispatch"
    assert job["concurrency"]["cancel-in-progress"] is True
    assert 0 < job["timeout-minutes"] <= 70
    run_steps = " ".join(step.get("run", "") for step in job["steps"])
    assert "dispatch_deploy_after_auto_merge.py" in run_steps
