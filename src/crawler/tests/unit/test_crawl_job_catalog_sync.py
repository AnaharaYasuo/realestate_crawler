# -*- coding: utf-8 -*-
"""Offline sync gate: CRAWL_JOBS must resolve to Start API + seed URL + dispatch."""
from __future__ import annotations

import pytest

from package.utils.crawl_job_catalog import build_catalog, unresolved_jobs
from package.utils.crawl_jobs import CRAWL_JOBS


def test_crawl_jobs_not_empty():
    assert len(CRAWL_JOBS) >= 80


def test_catalog_covers_all_crawl_jobs():
    missing = unresolved_jobs()
    assert missing == [], (
        "Crawl catalog could not resolve Start API / seed URL for jobs:\n"
        + "\n".join(f"  - {c}/{t}" for c, t in missing)
    )


def test_catalog_seed_urls_are_http():
    catalog = build_catalog()
    for job, target in catalog.items():
        assert target.seed_url.startswith("http"), f"{job} seed is not http: {target.seed_url}"
        assert target.api_module
        assert target.start_class.endswith("StartAsync")


def test_dispatch_map_covers_all_crawl_jobs():
    """Every production job must be registered in main.get_dispatch_map()."""
    # Importing main pulls Flask routes; skip only when optional deps are missing.
    try:
        import main as crawler_main
    except ModuleNotFoundError as exc:
        pytest.skip(f"main.get_dispatch_map unavailable in this environment: {exc}")

    dispatch = crawler_main.get_dispatch_map()
    missing = [job for job in CRAWL_JOBS if job not in dispatch]
    assert missing == [], (
        "get_dispatch_map missing CRAWL_JOBS entries:\n"
        + "\n".join(f"  - {c}/{t}" for c, t in missing)
    )


def test_keikyu_kodate_start_class_follows_naming_convention():
    """Regression: misnamed ParseKeikyuStartAsync blocked catalog discovery."""
    from package.api.keikyu import ParseKeikyuKodateStartAsync

    catalog = build_catalog()
    target = catalog[("keikyu", "kodate")]
    assert target.start_class == "ParseKeikyuKodateStartAsync"
    assert issubclass(ParseKeikyuKodateStartAsync, object)
