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
MERGE_SHA = "4b41e2c1ff56173f97951ef3c5d82f10adfe9670"
OLD_SHA = "0b1ed815e7bb8596774d06e0adbe778fb124eefc"
NEWER_SHA = "9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f"
DEPLOYED = [{"status": "completed", "conclusion": "success"}]
OPEN = {"state": "OPEN", "mergeCommit": None}


class FakeGh:
    """Scripted gh runner. heads/runs values may be sequences consumed per call (last one sticks)."""

    def __init__(self, views=(), heads=(OLD_SHA,), runs=None, dispatch_rc=0, open_prs="[]"):
        self.views = list(views)
        self.heads = list(heads)
        self.runs = {sha: list(v) for sha, v in (runs or {}).items()}
        self.dispatch_rc = dispatch_rc
        self.open_prs = open_prs
        self.calls = []

    @staticmethod
    def _next(queue):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def _view(self):
        item = self._next(self.views)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, tuple):
            return item
        return 0, json.dumps(item)

    def _runs(self, sha):
        queue = self.runs.get(sha, [[]])
        runs = self._next(queue)
        return (1, "") if runs is None else (0, json.dumps(runs))

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "view"]:
            return self._view()
        if args[:2] == ["pr", "list"]:
            return (1, "") if self.open_prs is None else (0, self.open_prs)
        if args[:2] == ["run", "list"]:
            return self._runs(args[args.index("--commit") + 1])
        if args[:1] == ["api"] and args[1].endswith("/branches/production"):
            head = self._next(self.heads)
            return (1, "") if head is None else (0, head + "\n")
        if args[:2] == ["workflow", "run"]:
            return self.dispatch_rc, ""
        raise AssertionError(f"unexpected gh call: {args}")

    @property
    def dispatch_calls(self):
        return [c for c in self.calls if c[:2] == ["workflow", "run"]]

    def run_list_calls(self, sha):
        return [c for c in self.calls if c[:2] == ["run", "list"] and sha in c]


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, sec):
        self.sleeps.append(sec)
        self.now += sec


def _merged(sha=MERGE_SHA):
    return {"state": "MERGED", "mergeCommit": {"oid": sha}}


def _no_sleep(_sec):
    return None


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
    assert dd.has_deploy_run(FakeGh(runs={MERGE_SHA: [runs]}), MERGE_SHA) is expected


def test_has_deploy_run_treats_timeout_as_unknown():
    def gh(_args):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=10)

    assert dd.has_deploy_run(gh, MERGE_SHA) is None


def test_lookup_retries_then_recovers():
    gh = FakeGh(runs={MERGE_SHA: [None, DEPLOYED]})
    clock = FakeClock()

    assert dd.lookup_deploy_run(gh, MERGE_SHA, sleep=clock.sleep) is True
    assert clock.sleeps == [dd.LOOKUP_RETRY_SEC]


def test_lookup_gives_up_after_bounded_attempts():
    gh = FakeGh(runs={MERGE_SHA: [None]})
    clock = FakeClock()

    assert dd.lookup_deploy_run(gh, MERGE_SHA, sleep=clock.sleep) is None
    assert len(gh.run_list_calls(MERGE_SHA)) == dd.LOOKUP_ATTEMPTS
    assert clock.sleeps == [dd.LOOKUP_RETRY_SEC] * (dd.LOOKUP_ATTEMPTS - 1)


def test_auto_merged_head_without_push_run_dispatches_after_grace():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[]]})
    clock = FakeClock()

    assert dd.ensure_production_deployed(gh, 90, sleep=clock.sleep) == dd.DISPATCH
    assert gh.dispatch_calls == [DISPATCH_CALL]
    assert clock.sleeps == [90]
    assert len(gh.run_list_calls(MERGE_SHA)) == 2


def test_already_deployed_head_returns_without_waiting():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [DEPLOYED]})
    clock = FakeClock()

    assert dd.ensure_production_deployed(gh, 90, sleep=clock.sleep) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == []
    assert clock.sleeps == []


def test_push_run_appearing_within_grace_prevents_dispatch():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[], [{"status": "queued", "conclusion": None}]]})

    assert dd.ensure_production_deployed(gh, 90, sleep=_no_sleep) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == []


def test_head_is_reread_after_grace_so_newer_deployed_head_is_not_redeployed():
    gh = FakeGh(heads=[MERGE_SHA, NEWER_SHA], runs={MERGE_SHA: [[]], NEWER_SHA: [DEPLOYED]})

    assert dd.ensure_production_deployed(gh, 90, sleep=_no_sleep) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == []
    assert gh.run_list_calls(NEWER_SHA)


@pytest.mark.parametrize(
    ("heads", "runs"),
    [
        ([None], {}),
        ([MERGE_SHA, None], {MERGE_SHA: [[]]}),
        ([MERGE_SHA], {MERGE_SHA: [None]}),
        ([MERGE_SHA], {MERGE_SHA: [[], None]}),
    ],
)
def test_lookup_failures_fail_without_dispatch(heads, runs):
    gh = FakeGh(heads=heads, runs=runs)

    assert dd.ensure_production_deployed(gh, 90, sleep=_no_sleep) == dd.LOOKUP_FAILED
    assert gh.dispatch_calls == []


def test_get_production_head_timeout_is_unknown():
    def gh(_args):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=10)

    assert dd.get_production_head(gh) is None


def test_dispatch_failure_is_reported():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[]]}, dispatch_rc=1)
    assert dd.ensure_production_deployed(gh, 0, sleep=_no_sleep) == dd.DISPATCH_FAILED


def test_dispatch_timeout_is_failure():
    def gh(_args):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=10)

    assert dd.dispatch_deploy(gh) == dd.DISPATCH_FAILED


@pytest.mark.parametrize(
    ("open_prs", "expected"),
    [('[{"number": 544}]', "544"), ("[]", ""), ("", ""), (None, None)],
)
def test_find_release_pr(open_prs, expected):
    assert dd.find_release_pr(FakeGh(open_prs=open_prs)) == expected


def test_wait_returns_merge_commit():
    gh = FakeGh(views=[OPEN, _merged()])
    clock = FakeClock()

    result = dd.wait_for_merge("544", 3600, 30, run_gh=gh, sleep=clock.sleep, clock=clock.time)

    assert result == (dd.MERGED, MERGE_SHA)
    assert clock.sleeps == [30]


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


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (dd.DISPATCH, 0),
        (dd.ALREADY_DEPLOYED, 0),
        (dd.SKIP_CLOSED, 0),
        (dd.TIMED_OUT, 0),
        (dd.DISPATCH_FAILED, 1),
        (dd.POLL_FAILED, 1),
        (dd.LOOKUP_FAILED, 1),
    ],
)
def test_exit_code(result, code):
    assert dd.exit_code_for(result) == code


@pytest.mark.parametrize(
    ("result", "prefix"),
    [(dd.DISPATCH_FAILED, "::error::"), (dd.POLL_FAILED, "::error::"),
     (dd.LOOKUP_FAILED, "::error::"), (dd.TIMED_OUT, "::warning::"), (dd.DISPATCH, "")],
)
def test_annotation_for(result, prefix):
    assert dd.annotation_for(result) == prefix


def test_main_reconciles_then_deploys_auto_merged_pr():
    gh = FakeGh(views=[_merged()], heads=[OLD_SHA, MERGE_SHA],
                runs={OLD_SHA: [DEPLOYED], MERGE_SHA: [[]]})
    code = dd.main(["--pr-number", "544", "--grace-sec", "0"], run_gh=gh, sleep=_no_sleep,
                   clock=lambda: 0.0)
    assert code == 0
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_startup_reconcile_recovers_missed_merge():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[]]}, open_prs="[]")
    assert dd.main(["--pr-number", ""], run_gh=gh, sleep=_no_sleep) == 0
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_without_pr_number_and_no_open_pr_only_reconciles():
    gh = FakeGh(runs={OLD_SHA: [DEPLOYED]}, open_prs="[]")
    assert dd.main(["--pr-number", ""], run_gh=gh, sleep=_no_sleep) == 0
    assert not any(c[:2] == ["pr", "view"] for c in gh.calls)
    assert gh.dispatch_calls == []


def test_main_without_pr_number_reacquires_open_release_pr():
    gh = FakeGh(views=[_merged()], heads=[OLD_SHA, MERGE_SHA],
                runs={OLD_SHA: [DEPLOYED], MERGE_SHA: [[]]}, open_prs='[{"number": 544}]')
    code = dd.main(["--pr-number", "", "--grace-sec", "0"], run_gh=gh, sleep=_no_sleep,
                   clock=lambda: 0.0)
    assert code == 0
    assert ["pr", "view", "544", "--json", "state,mergeCommit"] in gh.calls
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_without_open_pr_rechecks_head_merged_after_startup():
    gh = FakeGh(heads=[OLD_SHA, MERGE_SHA], runs={OLD_SHA: [DEPLOYED], MERGE_SHA: [[]]},
                open_prs="[]")
    assert dd.main(["--pr-number", "", "--grace-sec", "0"], run_gh=gh, sleep=_no_sleep) == 0
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_redispatches_only_for_a_newer_head_after_startup_dispatch():
    gh = FakeGh(views=[_merged()], heads=[MERGE_SHA, MERGE_SHA, NEWER_SHA],
                runs={MERGE_SHA: [[]], NEWER_SHA: [[]]})
    code = dd.main(["--pr-number", "544", "--grace-sec", "0"], run_gh=gh, sleep=_no_sleep,
                   clock=lambda: 0.0)
    assert code == 0
    assert gh.dispatch_calls == [DISPATCH_CALL, DISPATCH_CALL]


def test_ensure_skips_head_already_dispatched_in_this_run():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[]]})
    dispatched = set()
    assert dd.ensure_production_deployed(gh, 0, sleep=_no_sleep, dispatched=dispatched) == dd.DISPATCH
    assert dispatched == {MERGE_SHA}
    assert dd.ensure_production_deployed(gh, 0, sleep=_no_sleep, dispatched=dispatched) == dd.ALREADY_DEPLOYED
    assert gh.dispatch_calls == [DISPATCH_CALL]


def test_main_without_open_pr_fails_when_recheck_fails():
    gh = FakeGh(heads=[OLD_SHA, None], runs={OLD_SHA: [DEPLOYED]}, open_prs="[]")
    assert dd.main(["--pr-number", ""], run_gh=gh, sleep=_no_sleep) == 1


def test_main_reconcile_only_skips_pr_wait():
    gh = FakeGh(heads=[MERGE_SHA], runs={MERGE_SHA: [[]]}, open_prs='[{"number": 544}]')
    assert dd.main(["--reconcile-only", "--grace-sec", "0"], run_gh=gh, sleep=_no_sleep) == 0
    assert gh.dispatch_calls == [DISPATCH_CALL]
    assert not any(c[:2] in (["pr", "view"], ["pr", "list"]) for c in gh.calls)


def test_main_reconcile_only_already_deployed_does_nothing():
    gh = FakeGh(runs={OLD_SHA: [DEPLOYED]})
    assert dd.main(["--reconcile-only"], run_gh=gh, sleep=_no_sleep) == 0
    assert gh.dispatch_calls == []


def test_main_fails_when_release_pr_lookup_fails():
    gh = FakeGh(runs={OLD_SHA: [DEPLOYED]}, open_prs=None)
    assert dd.main(["--pr-number", ""], run_gh=gh, sleep=_no_sleep) == 1


def test_main_fails_when_reconcile_fails():
    gh = FakeGh(heads=[None])
    assert dd.main(["--pr-number", "544"], run_gh=gh, sleep=_no_sleep) == 1
    assert not any(c[:2] == ["pr", "view"] for c in gh.calls)


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
    assert "!cancelled()" in job["if"]
    assert job["permissions"]["actions"] == "write"
    assert job["concurrency"]["group"] == "release-pr-deploy-dispatch"
    assert 0 < job["timeout-minutes"] <= 70
    run_steps = " ".join(step.get("run", "") for step in job["steps"])
    assert "dispatch_deploy_after_auto_merge.py" in run_steps
    assert "needs.create-or-update-release-pr.outputs.pr_number" in json.dumps(job["steps"])
    assert "github.event_name == 'push'" in job["if"]
    assert create_job["if"] == "github.event_name == 'push'"


def test_auto_release_pr_schedules_reconcile_only_job():
    workflow = _load("auto-release-pr.yml")
    assert _on(workflow)["schedule"][0]["cron"].split()[1] == "*/3"
    job = workflow["jobs"]["reconcile-production-deploy"]
    assert job["if"] == "github.event_name == 'schedule'"
    assert "needs" not in job
    assert job["permissions"]["actions"] == "write"
    assert job["concurrency"] == {"group": "release-pr-deploy-reconcile", "cancel-in-progress": False}
    watcher_group = workflow["jobs"]["dispatch-deploy-after-auto-merge"]["concurrency"]["group"]
    assert job["concurrency"]["group"] != watcher_group
    assert 0 < job["timeout-minutes"] <= 15
    run_steps = " ".join(step.get("run", "") for step in job["steps"])
    assert "dispatch_deploy_after_auto_merge.py --reconcile-only" in run_steps
