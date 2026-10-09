# -*- coding: utf-8 -*-
"""
Tests for selective crawl execution, zero-job container suppression, and workflow orchestration (Issue #801).
"""
import pytest
from unittest.mock import patch
from package.utils.crawl_jobs import filter_crawl_jobs
from package.utils.task_distribution import distribute_jobs


def test_filter_crawl_jobs_multiple_companies():
    """Verify comma-separated multiple companies filtering."""
    jobs = filter_crawl_jobs(company="sumifu,mitsui")
    assert jobs
    assert all(c in ("sumifu", "mitsui") for c, _ in jobs)
    assert ("sumifu", "mansion") in jobs
    assert ("mitsui", "mansion") in jobs
    assert ("tokyu", "mansion") not in jobs


def test_filter_crawl_jobs_multiple_types():
    """Verify comma-separated multiple property types filtering with or without company."""
    jobs = filter_crawl_jobs(company="sumifu", property_type="mansion,kodate")
    assert set(jobs) == {("sumifu", "mansion"), ("sumifu", "kodate")}

    # Without company, filtering by property_type only should work when specified
    jobs_type_only = filter_crawl_jobs(property_type="mansion,tochi")
    assert jobs_type_only
    assert all(p in ("mansion", "tochi") for _, p in jobs_type_only)
    assert ("mitsui", "mansion") in jobs_type_only
    assert ("mitsui", "tochi") in jobs_type_only
    assert ("mitsui", "kodate") not in jobs_type_only


def test_filter_crawl_jobs_combined_companies_and_types():
    """Verify AND-filtering between multiple companies and multiple types."""
    jobs = filter_crawl_jobs(company="sumifu,tokyu", property_type="mansion,tochi")
    assert set(jobs) == {
        ("sumifu", "mansion"),
        ("sumifu", "tochi"),
        ("tokyu", "mansion"),
        ("tokyu", "tochi"),
    }


def test_distribute_jobs_empty_when_no_matching():
    """Verify distribute_jobs returns empty list when task has no assigned jobs."""
    # When filtering yields only 1 job
    targeted_jobs = [("sumifu", "mansion")]
    
    # In 8 tasks mode
    # "sumifu", "mansion" goes to Task 0
    t0 = distribute_jobs(targeted_jobs, task_index=0, task_count=8)
    assert t0 == [("sumifu", "mansion")]

    t1 = distribute_jobs(targeted_jobs, task_index=1, task_count=8)
    assert t1 == []

    # In modulo mode (e.g. 4 tasks)
    t0_mod = distribute_jobs(targeted_jobs, task_index=0, task_count=4)
    assert t0_mod == [("sumifu", "mansion")]
    t1_mod = distribute_jobs(targeted_jobs, task_index=1, task_count=4)
    assert t1_mod == []


def test_filter_crawl_jobs_invalid_empty_tokens():
    """Verify ValueError is raised when company, property_type, or sites is comma-only/whitespace."""
    with pytest.raises(ValueError, match="No valid company tokens found"):
        filter_crawl_jobs(company=", , ")

    with pytest.raises(ValueError, match="No valid property_type tokens found"):
        filter_crawl_jobs(property_type=",")

    with pytest.raises(ValueError, match="No valid site tokens found"):
        filter_crawl_jobs(sites=", , ")


def test_zero_jobs_container_fast_exit():
    """Verify run_pipeline.py skips DB/ProxySQL startup, records COMPLETED, and exits 0 when assigned jobs is 0."""
    from scripts.ops import run_pipeline
    import sys

    # Simulate task_index=1, task_count=8 with targeted job only in task 0
    with patch.object(run_pipeline, "get_task_config", return_value=(1, 8)), \
         patch.object(run_pipeline, "_execute_startup_resources") as mock_startup, \
         patch.object(run_pipeline, "_execute_safety_teardown"), \
         patch.object(run_pipeline, "run_command") as mock_run_cmd, \
         patch.object(run_pipeline.CrawlerTaskExecution.objects, "update_or_create") as mock_record, \
         patch.object(sys, "argv", ["run_pipeline.py", "--company=sumifu", "--type=mansion"]):
        
        with pytest.raises(SystemExit) as exc_info:
            run_pipeline.main()
        
        # Must exit with 0 (clean skip)
        assert exc_info.value.code == 0
        # Resource startup or DB commands must NOT be called
        mock_startup.assert_not_called()
        mock_run_cmd.assert_not_called()
        # CrawlerTaskExecution should record COMPLETED
        mock_record.assert_called_once()
        _, kwargs = mock_record.call_args
        assert kwargs["defaults"]["status"] == "COMPLETED"
        assert kwargs["defaults"]["jobs_assigned"] == 0


def test_daily_pipeline_yaml_selective_crawl_and_task_count():
    """Verify daily_pipeline.yaml accepts selective parameters and defines dynamic taskCount."""
    import os
    import yaml

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    yaml_path = os.path.join(repo_root, "terraform", "workflows", "daily_pipeline.yaml")
    assert os.path.exists(yaml_path), f"daily_pipeline.yaml missing at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    main_steps = data["main"]["steps"]
    step_names = [next(iter(s.keys())) for s in main_steps]
    assert "initVars" in step_names
    assert "buildCrawlerArgs" in step_names

    # Check that overrides in runCrawlerTasks contains taskCount and containerOverrides
    try_step = next(s["tryPipeline"] for s in main_steps if "tryPipeline" in s)
    run_crawler_step = next(s["runCrawlerTasks"] for s in try_step["try"]["steps"] if "runCrawlerTasks" in s)
    body = run_crawler_step["args"]["body"]
    assert "overrides" in body
    assert "taskCount" in body["overrides"]
    assert "containerOverrides" in body["overrides"]

    # Check ML step includes containerOverrides with mlArgs or --skip-train
    run_ml_step = next(s["runMLAndEstimation"] for s in try_step["try"]["steps"] if "runMLAndEstimation" in s)
    ml_body = run_ml_step["args"]["body"]
    assert "overrides" in ml_body
    assert any("--skip-train" in str(c) or "mlArgs" in str(c) for c in ml_body["overrides"]["containerOverrides"])
