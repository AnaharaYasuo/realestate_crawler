"""Unit tests for local vs CI live-guarantee parallel plans."""
from __future__ import annotations

import pytest

from package.utils.crawl_jobs import CRAWL_JOBS
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


_MIXED_JOBS = [
    ("sumifu", "mansion"),
    ("odakyu", "kodate"),
    ("heim", "mansion"),
    ("athome", "mansion"),
    ("mizuho", "tochi"),
    ("sekisui", "kodate"),
    ("totate", "mansion"),
]

# Mirrors the live-guarantee matrix entries in .github/workflows/test.yml.
_CI_MATRIX_ENVS = [
    {"CRAWL_LIVE_BUCKETS": "static", "CRAWL_LIVE_STATIC_SHARD": "1/2"},
    {"CRAWL_LIVE_BUCKETS": "static", "CRAWL_LIVE_STATIC_SHARD": "2/2"},
    {"CRAWL_LIVE_BUCKETS": "pw-mizuho,pw-sekisui"},
    {"CRAWL_LIVE_BUCKETS": "pw-athome"},
]


def _plan_job_ids(plan) -> list[str]:
    return [
        job_id
        for inv in plan.invocations
        for job_id in inv.sites_csv.split(",")
        if job_id
    ]


def test_bucket_filter_keeps_only_requested_labels_in_order():
    plan = build_live_parallel_plan(
        _MIXED_JOBS,
        environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", "CRAWL_LIVE_BUCKETS": "pw-sekisui, pw-mizuho"},
    )
    assert [inv.label for inv in plan.invocations] == ["pw-mizuho", "pw-sekisui"]
    assert plan.invocations[0].sites_csv == "mizuho_tochi"
    assert plan.invocations[1].sites_csv == "sekisui_kodate"


def test_bucket_filter_static_only_drops_playwright():
    plan = build_live_parallel_plan(
        _MIXED_JOBS,
        environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", "CRAWL_LIVE_BUCKETS": "static"},
    )
    assert [inv.label for inv in plan.invocations] == ["static"]
    assert plan.invocations[0].sites_csv == "sumifu_mansion,odakyu_kodate,heim_mansion,totate_mansion"
    assert plan.invocations[0].xdist_n == "auto"


def test_bucket_filter_unset_or_blank_keeps_all():
    for env in ({}, {"CRAWL_LIVE_BUCKETS": "  "}):
        plan = build_live_parallel_plan(_MIXED_JOBS, environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", **env})
        assert [inv.label for inv in plan.invocations] == ["static", "pw-mizuho", "pw-sekisui", "pw-athome"]


def test_bucket_filter_unknown_label_raises():
    with pytest.raises(ValueError, match="CRAWL_LIVE_BUCKETS"):
        build_live_parallel_plan(_MIXED_JOBS, environ={"CRAWL_LIVE_BUCKETS": "static,pw-unknown"})


def test_bucket_filter_only_commas_raises():
    with pytest.raises(ValueError, match="CRAWL_LIVE_BUCKETS"):
        build_live_parallel_plan(_MIXED_JOBS, environ={"CRAWL_LIVE_BUCKETS": ",,"})


def test_static_shard_round_robin_split():
    env = {"CRAWL_LIVE_PARALLEL_MODE": "ci"}
    first = build_live_parallel_plan(_MIXED_JOBS, environ={**env, "CRAWL_LIVE_STATIC_SHARD": "1/2"})
    second = build_live_parallel_plan(_MIXED_JOBS, environ={**env, "CRAWL_LIVE_STATIC_SHARD": "2/2"})
    assert first.invocations[0].label == "static"
    assert first.invocations[0].sites_csv == "sumifu_mansion,heim_mansion"
    assert second.invocations[0].sites_csv == "odakyu_kodate,totate_mansion"
    # Shard only narrows static; Playwright buckets are untouched.
    assert [inv.label for inv in first.invocations[1:]] == ["pw-mizuho", "pw-sekisui", "pw-athome"]


def test_static_shard_one_of_one_is_identity():
    env = {"CRAWL_LIVE_PARALLEL_MODE": "ci"}
    base = build_live_parallel_plan(_MIXED_JOBS, environ=env)
    sharded = build_live_parallel_plan(_MIXED_JOBS, environ={**env, "CRAWL_LIVE_STATIC_SHARD": "1/1"})
    assert sharded == base


def test_static_shard_empty_drops_static_bucket():
    jobs = [("sumifu", "mansion"), ("athome", "mansion")]
    plan = build_live_parallel_plan(
        jobs,
        environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", "CRAWL_LIVE_STATIC_SHARD": "2/2"},
    )
    assert [inv.label for inv in plan.invocations] == ["pw-athome"]


@pytest.mark.parametrize("raw", ["0/2", "3/2", "1/0", "a/2", "1-2", "2", "1/2/3", "-1/2"])
def test_static_shard_invalid_raises(raw):
    with pytest.raises(ValueError, match="CRAWL_LIVE_STATIC_SHARD"):
        build_live_parallel_plan(_MIXED_JOBS, environ={"CRAWL_LIVE_STATIC_SHARD": raw})


def test_ci_matrix_split_covers_all_crawl_jobs_exactly_once():
    all_ids = [f"{c}_{t}" for c, t in CRAWL_JOBS]
    covered: list[str] = []
    for matrix_env in _CI_MATRIX_ENVS:
        plan = build_live_parallel_plan(
            CRAWL_JOBS, environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", **matrix_env}
        )
        assert plan.invocations, f"matrix entry selected nothing: {matrix_env}"
        covered.extend(_plan_job_ids(plan))
    assert len(covered) == len(set(covered)), "job selected by more than one matrix entry"
    assert sorted(covered) == sorted(all_ids)


def test_ci_matrix_playwright_entries_contain_no_static_jobs():
    for matrix_env in _CI_MATRIX_ENVS[2:]:
        plan = build_live_parallel_plan(
            CRAWL_JOBS, environ={"CRAWL_LIVE_PARALLEL_MODE": "ci", **matrix_env}
        )
        for job_id in _plan_job_ids(plan):
            assert job_id.split("_", 1)[0].lower() in PLAYWRIGHT_COMPANIES
