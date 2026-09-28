"""Issue #546: auto-merge by GITHUB_TOKEN must still trigger exactly one production deploy."""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ops import dispatch_deploy_after_auto_merge as dd

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
DISPATCH_CALL = ["workflow", "run", "deploy-production.yml", "--ref", "production"]
MERGE_SHA = "4b41e2c"
HEAD_SHA = "0b1ed81"


class FakeGh:
    """Scripted gh runner keyed by command shape; records every call."""

    def __init__(self, views=(), runs=None, head=HEAD_SHA, head_date="2026-09-28T00:00:00Z",
                 dispatch_rc=0, open_prs="[]"):
        self.views = list(views)
        self.runs = runs or {}
        self.head = head
        self.head_date = head_date
        self.dispatch_rc = dispatch_rc
        self.open_prs = open_prs
        self.calls = []

    def _view(self):
        item = self.views.pop(0) if len(self.views) > 1 else self.views[0]
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, tuple):
            return item
        return 0, json.dumps(item)

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "view"]:
            return self._view()
        if args[:2] == ["pr", "list"]:
            return (1, "") if self.open_prs is None else (0, self.open_prs)
        if args[:2] == ["run", "list"]:
            sha = args[args.index("--commit") + 1]
            runs = self.runs.get(sha, [])
            return (1, "") if runs is None else (0, json.dumps(runs))
        if args[:1] == ["api"] and args[1].endswith("/branches/production"):
            return (0, self.head) if self.head else (1, "")
        if args[:1] == ["api"] and "/commits/" in args[1]:
            return (1, "") if self.head_date is None else (0, self.head_date)
        if args[:2] == ["workflow", "run"]:
            return self.dispatch_rc, ""
        raise AssertionError(f"unexpected gh call: {args}")

    @property
    def dispatch_calls(self):
        return [c for c in self.calls if c[:2] == ["workflow", "run"]]


class FakeClock:
    def __init__(self, wall=0.0):
        self.now = 0.0
        self.wall_now = wall
        self.sleeps = []

    def time(self):
        return self.now

    def wall(self):
        return self.wall_now + self.now

    def sleep(self, sec):
        self.sleeps.append(sec)
        self.now += sec


def _merged(sha=MERGE_SHA):
    return {"state": "MERGED", "mergeCommit": {"oid": sha}}


OPEN = {"state": "OPEN", "mergeCommit": None}
DEPLOYED = [{"status": "completed", "conclusion": "success"}]


@pytest.mark.parametrize(
    ("state", "expected"),
    [("MERGED", dd.MERGED), ("CLOSED", dd.SKIP_CLOSED), ("OPEN", dd.WAIT), (None, dd.WAIT)],
)
def test_decide_action(state, expected):
    assert dd.decide_action(state) == expected


@pytest.mark.parametrize(
    ("runs", "expected"),
    [
        ([], False),
        ([{"status": "completed", "conclusion": "cancelled"}], False),
        ([{"status": "in_progress", "conclusion": ""}], True),
        ([{"status": "queued", "conclusion": None}], True),
        ([{"status": "completed", "conclusion": "failure"}], True),
        (DEPLOYED, True),
        ([{"status": "completed", "conclusion": "cancelled"}] + DEPLOYED, True),
        (None, None),
    ],
)
def test_has_deploy_run(runs, expected):
    assert dd.has_deploy_run(FakeGh(runs={MERGE_SHA: runs}), MERGE_SHA) is expected


def test_auto_merge_without_push_run_dispatches_once_after_grace():
    gh = FakeGh(views=[OPEN, _merged()], runs={HEAD_SHA: DEPLOYED, MERGE_SHA: []})
    clock = FakeClock()

    result = dd.wait_for_merge("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)
    assert result == (dd.MERGED, MERGE_SHA)
    assert dd.ensure_deployed(gh, MERGE_SHA, 90, sleep=clock.sleep) == dd.DISPATCH

    assert gh.dispatch_calls == [DISPATCH_CALL]
    assert clock.sleeps == [30, 90]


def test_human_merge_with_push_run_does_not_dispatch():
    gh = FakeGh(views=[_merged()], runs={MERGE_SHA: DEPLOYED})
    clock = FakeClock()

    assert dd.ensure_deployed(gh, MERGE_SHA, 90, sleep=clock.sleep) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == []


def test_unknown_run_state_fails_after_retries_without_dispatch():
    gh = FakeGh(runs={MERGE_SHA: None})
    clock = FakeClock()

    assert dd.ensure_deployed(gh, MERGE_SHA, 0, sleep=clock.sleep) == dd.LOOKUP_FAILED
    assert gh.dispatch_calls == []
    assert len([c for c in gh.calls if c[:2] == ["run", "list"]]) == dd.LOOKUP_ATTEMPTS


def test_lookup_recovers_on_retry():
    class Flaky(FakeGh):
        def __init__(self):
            super().__init__(runs={MERGE_SHA: []})
            self.failures = 1

        def __call__(self, args):
            if args[:2] == ["run", "list"] and self.failures:
                self.failures -= 1
                self.calls.append(args)
                return 1, ""
            return super().__call__(args)

    gh = Flaky()
    assert dd.ensure_deployed(gh, MERGE_SHA, 0, sleep=lambda _s: None) == dd.DISPATCH
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_dispatch_failure_is_reported():
    gh = FakeGh(runs={MERGE_SHA: []}, dispatch_rc=1)
    assert dd.ensure_deployed(gh, MERGE_SHA, 0, sleep=lambda _s: None) == dd.DISPATCH_FAILED


def test_closed_without_merge():
    gh = FakeGh(views=[{"state": "CLOSED", "mergeCommit": None}])
    clock = FakeClock()
    assert dd.wait_for_merge("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time) == (
        dd.SKIP_CLOSED, None)


def test_wait_is_finite():
    gh = FakeGh(views=[OPEN])
    clock = FakeClock()

    result = dd.wait_for_merge("544", 90, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == (dd.TIMED_OUT, None)
    assert sum(clock.sleeps) <= 90


def test_transient_errors_keep_waiting_and_reset():
    gh = FakeGh(views=[
        subprocess.TimeoutExpired(cmd="gh", timeout=10),
        (1, ""),
        OPEN,
        (0, "not json"),
        (1, ""),
        _merged(),
    ])
    clock = FakeClock()

    result = dd.wait_for_merge("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time,
                               max_errors=3)
    assert result == (dd.MERGED, MERGE_SHA)


def test_consecutive_errors_fail_instead_of_silent_success():
    gh = FakeGh(views=[(1, "")])
    clock = FakeClock()

    result = dd.wait_for_merge("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time,
                               max_errors=3)
    assert result == (dd.POLL_FAILED, None)
    assert len([c for c in gh.calls if c[:2] == ["pr", "view"]]) == 3


def test_reconcile_dispatches_undeployed_old_production_head():
    gh = FakeGh(runs={HEAD_SHA: []}, head_date="2026-09-28T14:00:15Z")
    clock = FakeClock(wall=dd.parse_iso8601("2026-09-28T14:10:00Z"))

    assert dd.reconcile_production(gh, 90, wall_clock=clock.wall) == dd.DISPATCH
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_reconcile_skips_recent_head_to_avoid_racing_push_run():
    gh = FakeGh(runs={HEAD_SHA: []}, head_date="2026-09-28T14:00:15Z")
    clock = FakeClock(wall=dd.parse_iso8601("2026-09-28T14:01:00Z"))

    assert dd.reconcile_production(gh, 90, wall_clock=clock.wall) == dd.SKIP_RECENT
    assert gh.dispatch_calls == []


@pytest.mark.parametrize("head_date", ["garbage", None])
def test_reconcile_fails_when_commit_date_unavailable(head_date):
    gh = FakeGh(runs={HEAD_SHA: []}, head_date=head_date)
    assert dd.reconcile_production(gh, 90, wall_clock=lambda: 1e10) == dd.LOOKUP_FAILED
    assert gh.dispatch_calls == []


def test_reconcile_fails_when_run_lookup_unavailable():
    gh = FakeGh(runs={HEAD_SHA: None})
    assert dd.reconcile_production(gh, 90, wall_clock=lambda: 1e10,
                                   sleep=lambda _s: None) == dd.LOOKUP_FAILED
    assert gh.dispatch_calls == []


@pytest.mark.parametrize(
    ("result", "prefix"),
    [(dd.DISPATCH_FAILED, "::error::"), (dd.POLL_FAILED, "::error::"),
     (dd.TIMED_OUT, "::warning::"), (dd.DISPATCH, "")],
)
def test_annotation_for(result, prefix):
    assert dd.annotation_for(result) == prefix


def test_reconcile_skips_already_deployed_head():
    gh = FakeGh(runs={HEAD_SHA: DEPLOYED})
    assert dd.reconcile_production(gh, 90, wall_clock=lambda: 1e10) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == []


def test_reconcile_fails_when_head_unknown():
    gh = FakeGh(head=None)
    assert dd.reconcile_production(gh, 90, wall_clock=lambda: 1e10) == dd.LOOKUP_FAILED


@pytest.mark.parametrize(
    ("open_prs", "expected"),
    [('[{"number": 544}]', "544"), ("[]", ""), ("", ""), (None, None)],
)
def test_find_release_pr(open_prs, expected):
    assert dd.find_release_pr(FakeGh(open_prs=open_prs)) == expected


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (dd.DISPATCH, 0),
        (dd.ALREADY_DEPLOYED, 0),
        (dd.SKIP_CLOSED, 0),
        (dd.SKIP_RECENT, 0),
        (dd.TIMED_OUT, 0),
        (dd.DISPATCH_FAILED, 1),
        (dd.POLL_FAILED, 1),
        (dd.LOOKUP_FAILED, 1),
    ],
)
def test_exit_code(result, code):
    assert dd.exit_code_for(result) == code


def test_main_reconciles_then_deploys_merged_pr():
    gh = FakeGh(views=[_merged()], runs={HEAD_SHA: DEPLOYED, MERGE_SHA: []})
    code = dd.main(["--pr-number", "544", "--grace-sec", "0"], run_gh=gh, sleep=lambda _s: None,
                   clock=lambda: 0.0, wall_clock=lambda: 1e10)
    assert code == 0
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_without_pr_number_and_no_open_pr_only_reconciles():
    gh = FakeGh(runs={HEAD_SHA: DEPLOYED}, open_prs="[]")
    assert dd.main(["--pr-number", ""], run_gh=gh, wall_clock=lambda: 1e10) == 0
    assert not any(c[:2] == ["pr", "view"] for c in gh.calls)
    assert gh.dispatch_calls == []


def test_main_without_pr_number_reacquires_open_release_pr():
    gh = FakeGh(views=[_merged()], runs={HEAD_SHA: DEPLOYED, MERGE_SHA: []},
                open_prs='[{"number": 544}]')
    code = dd.main(["--pr-number", "", "--grace-sec", "0"], run_gh=gh, sleep=lambda _s: None,
                   clock=lambda: 0.0, wall_clock=lambda: 1e10)
    assert code == 0
    assert ["pr", "view", "544", "--json", "state,mergeCommit"] in gh.calls
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_fails_when_release_pr_lookup_fails():
    gh = FakeGh(runs={HEAD_SHA: DEPLOYED}, open_prs=None)
    assert dd.main(["--pr-number", ""], run_gh=gh, wall_clock=lambda: 1e10) == 1


def test_main_fails_when_reconcile_dispatch_fails():
    gh = FakeGh(runs={HEAD_SHA: []}, dispatch_rc=1)
    assert dd.main(["--pr-number", ""], run_gh=gh, wall_clock=lambda: 1e10) == 1


def test_gh_calls_use_finite_timeout(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="x", stderr="")

    monkeypatch.setattr(dd.subprocess, "run", fake_run)
    assert dd.run_gh(["pr", "list"]) == (0, "x")
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


def test_auto_release_pr_passes_pr_number_to_dispatch_job():
    workflow = _load("auto-release-pr.yml")
    create_job = workflow["jobs"]["create-or-update-release-pr"]
    assert "pr_number" in create_job["outputs"]
    assert "GITHUB_OUTPUT" in " ".join(s.get("run", "") for s in create_job["steps"])

    job = workflow["jobs"]["dispatch-deploy-after-auto-merge"]
    assert job["needs"] == "create-or-update-release-pr"
    assert job["permissions"]["actions"] == "write"
    assert job["concurrency"]["group"] == "release-pr-deploy-dispatch"
    assert 0 < job["timeout-minutes"] <= 70
    run_steps = " ".join(step.get("run", "") for step in job["steps"])
    assert "dispatch_deploy_after_auto_merge.py" in run_steps
    assert "needs.create-or-update-release-pr.outputs.pr_number" in json.dumps(job["steps"])
