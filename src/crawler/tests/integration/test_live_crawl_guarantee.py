"""
Full-matrix live crawl guarantee test (fast + parallel).

Per-job budget via CRAWL_SMOKE_JOB_BUDGET_SEC (default 10).
Suite wall-clock target: ≤300s via environment-aware buckets
(package.utils.live_parallel / run_live_crawl_guarantee.py):
  local → static -n 4 ∥ (mizuho → (sekisui ∥ athome))
  CI    → static -n auto ∥ (mizuho → (sekisui ∥ athome))

Site-scoped runs (fix verification without full matrix):
  CRAWL_GUARANTEE_SITES=sumifu,odakyu
  CRAWL_GUARANTEE_SITES=sumifu_mansion,odakyu_investment
  CRAWL_GUARANTEE_COMPANY=sumifu  (+ optional CRAWL_GUARANTEE_TYPE=mansion)
  task test-live SITES=sumifu,odakyu
  task test-live COMPANY=sumifu TYPE=mansion
  task test-live MODE=ci
"""
from __future__ import annotations

import os
import pytest
from package.utils.crawl_job_catalog import build_catalog, get_target
from package.utils.crawl_jobs import CRAWL_JOBS, jobs_from_env
from package.utils.crawl_smoke_engine import _effective_job_budget_sec, run_smoke_sync

JOBS = jobs_from_env(list(CRAWL_JOBS))
JOB_IDS = [f"{company}_{ptype}" for company, ptype in JOBS]


@pytest.mark.live
def test_catalog_complete_before_live_smoke():
    catalog = build_catalog()
    # Scoped runs only require selected jobs to resolve; full matrix still checks all.
    check_jobs = JOBS if JOBS != list(CRAWL_JOBS) else list(CRAWL_JOBS)
    missing = [job for job in check_jobs if job not in catalog]
    assert not missing, f"Cannot run live guarantee; unresolved jobs: {missing}"


@pytest.mark.live
@pytest.mark.parametrize("job", JOBS, ids=JOB_IDS)
def test_live_crawl_guarantee_for_job(job):
    """
    Production-path smoke:
    seed -> production parsers -> >=1 detail URL -> required fields.
    """
    company, property_type = job
    target = get_target(company, property_type)
    budget = _effective_job_budget_sec(company, property_type=property_type)
    result = run_smoke_sync(target)
    # Allow modest overrun for in-flight HTTP/PW wind-down after deadline.
    overrun = 25.0 if result.parsed_ok > 0 else 2.0
    ci_network_errors = (
        "WAF",
        "403",
        "TimeoutError",
        "ConnectTimeout",
        "ClientConnectorError",
        "ServerDisconnectedError",
        "ConnectionResetError",
    )
    is_ci = bool(
        os.getenv("GITHUB_ACTIONS")
        or os.getenv("CI")
        or os.getenv("CRAWL_LIVE_PARALLEL_MODE") == "ci"
    )
    if (result.detail_urls_found == 0 or result.parsed_ok == 0) and is_ci and any(
        any(sig in str(e) for sig in ci_network_errors) for e in result.errors
    ):
        pytest.skip(
            f"[{target.job_id}] Skipped due to CI datacenter IP WAF/network block: {result.errors}"
        )
    assert result.elapsed_sec <= budget + overrun, (
        f"[{target.job_id}] too slow: {result.elapsed_sec:.1f}s (budget {budget:.0f}s)"
    )
    assert result.detail_urls_found > 0, (
        f"[{target.job_id}] ZERO DETAIL URLS from {target.seed_url}. Errors: {result.errors}"
    )
    assert result.parsed_ok > 0, (
        f"[{target.job_id}] No successful detail parses. Errors: {result.errors}"
    )
    assert result.paging_ok, (
        f"[{target.job_id}] paging failed "
        f"(pages={result.pages_fetched}, exhausted={result.paging_exhausted}). "
        f"Errors: {result.errors}"
    )
    assert result.property_type_ok, (
        f"[{target.job_id}] property type check failed. Errors: {result.errors}"
    )
    assert not result.errors, f"[{target.job_id}] Smoke errors: {result.errors}"
