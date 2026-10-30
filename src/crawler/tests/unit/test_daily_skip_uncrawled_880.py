# -*- coding: utf-8 -*-
"""
Unit tests for excluding un-crawled sites from scheduled cloud pipeline (Issue #880).
"""
import os
import yaml
from package.utils.crawl_jobs import CRAWL_JOBS, UNCRAWLED_COMPANIES, PORTAL_COMPANIES, filter_crawl_jobs
from package.ml.evaluation.targets import get_all_property_models


def test_uncrawled_companies_constant():
    """Verify UNCRAWLED_COMPANIES contains the target un-crawled sites."""
    expected = {"kenbiya", "ietan", "haseko", "adcast", "toho"}
    assert UNCRAWLED_COMPANIES == expected
    assert PORTAL_COMPANIES == {"athome", "homes"}


def test_filter_crawl_jobs_skip_uncrawled():
    """Verify filter_crawl_jobs filters out UNCRAWLED_COMPANIES when requested."""
    all_jobs = list(CRAWL_JOBS)
    
    # 1. Without skip
    assert any(c in UNCRAWLED_COMPANIES for c, _ in all_jobs)
    
    # 2. With skip_uncrawled
    filtered = filter_crawl_jobs(all_jobs, skip_uncrawled=True)
    assert not any(c in UNCRAWLED_COMPANIES for c, _ in filtered)


def test_daily_pipeline_yaml_skip_uncrawled_configuration():
    """Verify daily_pipeline.yaml defines skipUncrawled argument and passes --skip-uncrawled."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    yaml_path = os.path.join(repo_root, "terraform", "workflows", "daily_pipeline.yaml")
    assert os.path.exists(yaml_path), f"daily_pipeline.yaml missing at {yaml_path}"

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    main_steps = data["main"]["steps"]
    init_vars = next(s["initVars"]["assign"] for s in main_steps if "initVars" in s)
    init_dict = {next(iter(item.keys())): next(iter(item.values())) for item in init_vars}

    # Verify skipUncrawled in initVars
    assert "skipUncrawled" in init_dict
    assert "default(map.get(args, \"skipUncrawled\"), true)" in str(init_dict["skipUncrawled"])

    # Verify buildCrawlerArgs handles skipUncrawled
    build_crawler_args = next(s["buildCrawlerArgs"]["steps"] for s in main_steps if "buildCrawlerArgs" in s)
    step_keys = [next(iter(st.keys())) for st in build_crawler_args]
    assert "checkSkipUncrawled" in step_keys

    check_skip_uncrawled = next(st["checkSkipUncrawled"] for st in build_crawler_args if "checkSkipUncrawled" in st)
    switch_cond = check_skip_uncrawled["switch"][0]
    assert switch_cond["condition"] == "${skipUncrawled}"
    assigns = str(switch_cond["assign"])
    assert "--skip-uncrawled" in assigns


def test_scheduler_tf_passes_skip_uncrawled():
    """Verify scheduler.tf passes skipUncrawled=true to daily_pipeline_workflow execution."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    scheduler_path = os.path.join(repo_root, "terraform", "scheduler.tf")
    assert os.path.exists(scheduler_path), f"scheduler.tf missing at {scheduler_path}"

    with open(scheduler_path, encoding="utf-8") as f:
        content = f.read()

    assert "skipUncrawled" in content
    assert "skipUncrawled    = true" in content or "skipUncrawled   = true" in content or "\"skipUncrawled\": true" in content


def test_get_all_property_models_skip_uncrawled():
    """Verify get_all_property_models filters out uncrawled companies when requested."""
    all_models = get_all_property_models(skip_portals=False, skip_uncrawled=False)
    filtered_models = get_all_property_models(skip_portals=False, skip_uncrawled=True)

    # Some models belong to uncrawled companies
    all_names = {m.__name__.lower() for m in all_models}
    filtered_names = {m.__name__.lower() for m in filtered_models}

    assert len(filtered_models) < len(all_models)
    for uncrawled in UNCRAWLED_COMPANIES:
        assert not any(uncrawled in name for name in filtered_names)
        assert any(uncrawled in name for name in all_names)
