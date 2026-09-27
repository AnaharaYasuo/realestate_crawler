"""Unit tests for run_live_crawl_guarantee split-configuration guards."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.ops import run_live_crawl_guarantee as runner

_SPLIT_KEYS = (
    "CRAWL_LIVE_BUCKETS",
    "CRAWL_LIVE_STATIC_SHARD",
    "CRAWL_GUARANTEE_SITES",
    "CRAWL_GUARANTEE_COMPANY",
    "CRAWL_GUARANTEE_TYPE",
)


@pytest.fixture(autouse=True)
def _clean_split_env(monkeypatch):
    for key in _SPLIT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CRAWL_LIVE_PARALLEL_MODE", "ci")


def test_invalid_bucket_label_fails_without_running(monkeypatch):
    monkeypatch.setenv("CRAWL_LIVE_BUCKETS", "pw-nope")
    with patch.object(runner, "_run_plan") as run_plan:
        assert runner.main([]) == 2
    run_plan.assert_not_called()


def test_invalid_static_shard_fails_without_running(monkeypatch):
    monkeypatch.setenv("CRAWL_LIVE_STATIC_SHARD", "3/2")
    with patch.object(runner, "_run_plan") as run_plan:
        assert runner.main([]) == 2
    run_plan.assert_not_called()


def test_split_selecting_nothing_fails(monkeypatch):
    # Static-only scope filtered down to Playwright buckets -> empty plan.
    monkeypatch.setenv("CRAWL_GUARANTEE_SITES", "sumifu_mansion")
    monkeypatch.setenv("CRAWL_LIVE_BUCKETS", "pw-athome")
    with patch.object(runner, "_run_plan") as run_plan:
        assert runner.main([]) == 2
    run_plan.assert_not_called()


def test_split_runs_only_selected_buckets(monkeypatch):
    monkeypatch.setenv("CRAWL_LIVE_BUCKETS", "pw-mizuho,pw-sekisui")
    with patch.object(runner, "_run_plan", return_value=[0, 0]) as run_plan:
        assert runner.main([]) == 0
    plan = run_plan.call_args.args[0]
    assert [inv.label for inv in plan.invocations] == ["pw-mizuho", "pw-sekisui"]


def test_split_bucket_failure_propagates(monkeypatch):
    monkeypatch.setenv("CRAWL_LIVE_BUCKETS", "pw-athome")
    with patch.object(runner, "_run_plan", return_value=[1]):
        assert runner.main([]) == 1
