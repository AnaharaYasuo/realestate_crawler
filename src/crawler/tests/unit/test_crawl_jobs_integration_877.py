"""Unit tests verifying Kenbiya and Mid Brokers integration into CRAWL_JOBS and dispatch (#877)."""
from package.utils.crawl_jobs import CRAWL_JOBS, filter_crawl_jobs
from package.utils.crawl_job_catalog import build_catalog, unresolved_jobs


def test_kenbiya_jobs_registered_in_crawl_jobs():
    kenbiya_jobs = filter_crawl_jobs(sites="kenbiya")
    expected_types = {"mansion", "kodate", "tochi", "invest_apartment", "invest_building"}
    actual_types = {ptype for comp, ptype in kenbiya_jobs}
    assert actual_types == expected_types
    for ptype in expected_types:
        assert ("kenbiya", ptype) in CRAWL_JOBS


def test_mid_brokers_jobs_registered_in_crawl_jobs():
    expected_broker_jobs = [
        ("ietan", "mansion"),
        ("ietan", "kodate"),
        ("ietan", "tochi"),
        ("haseko", "mansion"),
        ("adcast", "kodate"),
        ("adcast", "tochi"),
        ("toho", "mansion"),
        ("toho", "kodate"),
        ("toho", "tochi"),
    ]
    for comp, ptype in expected_broker_jobs:
        assert (comp, ptype) in CRAWL_JOBS, f"Missing job in CRAWL_JOBS: {comp}_{ptype}"


def test_catalog_resolves_all_new_sites():
    missing = unresolved_jobs()
    assert missing == [], f"Unresolved jobs found: {missing}"

    catalog = build_catalog()
    # Check kenbiya resolution
    for ptype in ["mansion", "kodate", "tochi", "invest_apartment", "invest_building"]:
        target = catalog[("kenbiya", ptype)]
        assert target.company == "kenbiya"
        assert target.property_type == ptype
        assert target.seed_url.startswith("http")
        assert target.start_class.startswith("ParseKenbiya")

    # Check mid brokers resolution
    for comp, ptype in [("ietan", "mansion"), ("haseko", "mansion"), ("adcast", "kodate"), ("toho", "mansion")]:
        target = catalog[(comp, ptype)]
        assert target.company == comp
        assert target.property_type == ptype
        assert target.seed_url.startswith("http")


def test_dispatch_map_has_all_new_handlers():
    import main as crawler_main
    dispatch = crawler_main.get_dispatch_map()

    required_jobs = [
        ("kenbiya", "mansion"),
        ("kenbiya", "kodate"),
        ("kenbiya", "tochi"),
        ("kenbiya", "invest_apartment"),
        ("kenbiya", "invest_building"),
        ("ietan", "mansion"),
        ("ietan", "kodate"),
        ("ietan", "tochi"),
        ("haseko", "mansion"),
        ("adcast", "kodate"),
        ("adcast", "tochi"),
        ("toho", "mansion"),
        ("toho", "kodate"),
        ("toho", "tochi"),
    ]
    for job in required_jobs:
        assert job in dispatch, f"Missing handler in dispatch map for {job}"
        assert callable(dispatch[job])
