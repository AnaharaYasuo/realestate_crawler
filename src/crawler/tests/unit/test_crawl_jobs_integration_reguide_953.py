"""Unit tests verifying RE-Guide integration into CRAWL_JOBS and ML pipeline (Issue #953)."""
from package.ml.constants import COMPANIES
from package.utils.crawl_job_catalog import build_catalog
from package.utils.crawl_jobs import CRAWL_JOBS, filter_crawl_jobs


def test_reguide_in_crawl_jobs():
    """("reguide", "investment") must be present in CRAWL_JOBS."""
    assert ("reguide", "investment") in CRAWL_JOBS


def test_reguide_in_ml_companies():
    """'reguide' must be registered in package.ml.constants.COMPANIES."""
    assert "reguide" in COMPANIES


def test_reguide_filter_crawl_jobs():
    """filter_crawl_jobs correctly filters reguide jobs."""
    matched = filter_crawl_jobs(company="reguide")
    assert matched == [("reguide", "investment")]

    matched_site = filter_crawl_jobs(sites="reguide:investment")
    assert matched_site == [("reguide", "investment")]


def test_reguide_catalog_resolution():
    """build_catalog resolves Start API and seed URL for reguide investment."""
    catalog = build_catalog()
    assert ("reguide", "investment") in catalog
    target = catalog[("reguide", "investment")]
    assert target.company == "reguide"
    assert target.property_type == "investment"
    assert target.api_module == "reguide"
    assert target.start_class == "ParseReguideInvestmentStartAsync"
    assert target.seed_url.startswith("http")
