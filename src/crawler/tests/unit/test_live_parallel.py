"""Unit tests for local vs CI live-guarantee parallel plans."""
from __future__ import annotations

from package.utils.live_parallel import (
    PLAYWRIGHT_COMPANIES,
    build_live_parallel_plan,
    detect_live_parallel_mode,
    pytest_n_args,
    wall_limit_sec,
)


def test_detect_mode_defaults_to_local():
    assert detect_live_parallel_mode({}) == "local"
    assert detect_live_parallel_mode({"CI": "false"}) == "local"


def test_detect_mode_ci_from_github_actions():
    assert detect_live_parallel_mode({"GITHUB_ACTIONS": "true"}) == "ci"
    assert detect_live_parallel_mode({"CI": "true"}) == "ci"


def test_detect_mode_explicit_override_wins():
    assert detect_live_parallel_mode({"GITHUB_ACTIONS": "true", "CRAWL_LIVE_PARALLEL_MODE": "local"}) == "local"
    assert detect_live_parallel_mode({"CRAWL_LIVE_PARALLEL_MODE": "ci"}) == "ci"


def test_local_plan_caps_static_workers_and_serializes_playwright():
    jobs = [
        ("sumifu", "mansion"),
        ("odakyu", "kodate"),
        ("athome", "mansion"),
        ("mizuho", "tochi"),
        ("sekisui", "kodate"),
    ]
    plan = build_live_parallel_plan(jobs, environ={"CRAWL_LIVE_PARALLEL_MODE": "local"})
    assert plan.mode == "local"
    assert len(plan.invocations) == 4  # static + 3 PW companies
    static = plan.invocations[0]
    assert static.label == "static"
    # With Playwright buckets present, local static workers stay at the default cap
    # (one Chromium company at a time overlaps static).
    assert static.xdist_n == "4"
    assert "sumifu_mansion" in static.sites_csv
    assert "odakyu_kodate" in static.sites_csv
    assert "athome_mansion" not in static.sites_csv
    pw_labels = [inv.label for inv in plan.invocations[1:]]
    assert pw_labels == ["pw-mizuho", "pw-sekisui", "pw-athome"]
    assert all(inv.xdist_n == "0" for inv in plan.invocations[1:])
    assert plan.invocations[1].sites_csv == "mizuho_tochi"


def test_local_static_only_uses_full_xdist_default():
    jobs = [("sumifu", "mansion"), ("odakyu", "kodate")]
    plan = build_live_parallel_plan(jobs, environ={"CRAWL_LIVE_PARALLEL_MODE": "local"})
    assert len(plan.invocations) == 1
    assert plan.invocations[0].xdist_n == "4"


def test_ci_plan_uses_auto_for_static():
    jobs = [("heim", "mansion"), ("mizuho", "mansion")]
    plan = build_live_parallel_plan(jobs, environ={"GITHUB_ACTIONS": "true"})
    assert plan.mode == "ci"
    assert plan.invocations[0].xdist_n == "auto"
    assert plan.invocations[0].sites_csv == "heim_mansion"
    assert plan.invocations[1].label == "pw-mizuho"
    assert plan.invocations[1].sites_csv == "mizuho_mansion"
    assert plan.invocations[1].xdist_n == "0"


def test_scoped_static_only_is_single_invocation():
    jobs = [("sumifu", "mansion"), ("sumifu", "kodate")]
    plan = build_live_parallel_plan(jobs, environ={"CRAWL_LIVE_PARALLEL_MODE": "local"})
    assert len(plan.invocations) == 1
    assert plan.invocations[0].label == "static"
    assert plan.invocations[0].sites_csv == "sumifu_mansion,sumifu_kodate"


def test_scoped_playwright_only_skips_static_bucket():
    jobs = [("athome", "mansion"), ("athome", "kodate")]
    plan = build_live_parallel_plan(jobs, environ={"CRAWL_LIVE_PARALLEL_MODE": "ci"})
    assert len(plan.invocations) == 1
    assert plan.invocations[0].label == "pw-athome"
    assert plan.invocations[0].sites_csv == "athome_mansion,athome_kodate"


def test_local_worker_override_env():
    jobs = [("totate", "mansion")]
    plan = build_live_parallel_plan(
        jobs,
        environ={"CRAWL_LIVE_PARALLEL_MODE": "local", "CRAWL_LIVE_XDIST_LOCAL": "2"},
    )
    assert plan.invocations[0].xdist_n == "2"


def test_pytest_n_args():
    assert pytest_n_args("0") == []
    assert pytest_n_args("4") == ["-n", "4"]
    assert pytest_n_args("auto") == ["-n", "auto"]


def test_playwright_companies_frozen():
    assert PLAYWRIGHT_COMPANIES == frozenset({"athome", "mizuho", "sekisui"})


def test_wall_limit_sec_default_and_override():
    assert wall_limit_sec({}) == 300.0
    assert wall_limit_sec({"CRAWL_LIVE_WALL_LIMIT_SEC": "420"}) == 420.0
    assert wall_limit_sec({"CRAWL_LIVE_WALL_LIMIT_SEC": "bad"}) == 300.0
