"""Offline tests for CRAWL_JOBS site/company filtering (targeted live runs)."""
import pytest
from package.utils.crawl_jobs import CRAWL_JOBS, filter_crawl_jobs, jobs_from_env


def test_filter_empty_returns_all():
    assert filter_crawl_jobs() == list(CRAWL_JOBS)


def test_filter_by_company_token():
    jobs = filter_crawl_jobs(sites="sumifu")
    assert jobs
    assert all(c == "sumifu" for c, _ in jobs)
    assert ("sumifu", "mansion") in jobs
    assert ("sumifu", "invest_apartment") in jobs


def test_filter_by_job_id_and_colon():
    jobs = filter_crawl_jobs(sites="sumifu_mansion,odakyu:investment")
    assert jobs == [("sumifu", "mansion"), ("odakyu", "investment")]


def test_filter_company_and_type_env_style():
    jobs = filter_crawl_jobs(company="sumifu", property_type="kodate")
    assert jobs == [("sumifu", "kodate")]


def test_filter_unknown_token_raises():
    with pytest.raises(ValueError, match="Unknown"):
        filter_crawl_jobs(sites="not_a_real_broker")


def test_jobs_from_env_sites(monkeypatch):
    monkeypatch.setenv("CRAWL_GUARANTEE_SITES", "heim,keisei_mansion")
    monkeypatch.delenv("CRAWL_GUARANTEE_COMPANY", raising=False)
    monkeypatch.delenv("CRAWL_GUARANTEE_TYPE", raising=False)
    jobs = jobs_from_env()
    assert ("heim", "mansion") in jobs
    assert ("heim", "tochi") in jobs
    assert ("keisei", "mansion") in jobs
    assert all(c in ("heim", "keisei") for c, _ in jobs)
