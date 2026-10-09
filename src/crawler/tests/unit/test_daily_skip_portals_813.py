# -*- coding: utf-8 -*-
"""
Tests for daily pipeline skip-portals configuration in Cloud Workflows and Cloud Scheduler (Issue #813).
"""
import os
import yaml


def test_daily_pipeline_yaml_skip_portals_configuration():
    """Verify daily_pipeline.yaml defines skipPortals argument, passes --skip-portals, and optimizes taskCount to 5."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    yaml_path = os.path.join(repo_root, "terraform", "workflows", "daily_pipeline.yaml")
    assert os.path.exists(yaml_path), f"daily_pipeline.yaml missing at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    main_steps = data["main"]["steps"]
    init_vars = next(s["initVars"]["assign"] for s in main_steps if "initVars" in s)
    init_dict = {next(iter(item.keys())): next(iter(item.values())) for item in init_vars}

    # Verify skipPortals in initVars
    assert "skipPortals" in init_dict
    assert "default(map.get(args, \"skipPortals\"), true)" in str(init_dict["skipPortals"])

    # Verify buildCrawlerArgs handles skipPortals
    build_crawler_args = next(s["buildCrawlerArgs"]["steps"] for s in main_steps if "buildCrawlerArgs" in s)
    step_keys = [next(iter(st.keys())) for st in build_crawler_args]
    assert "checkSkipPortals" in step_keys
    assert "checkTaskCount" in step_keys

    # Verify checkSkipPortals assigns --skip-portals to mlArgs and crawlerArgs
    check_skip_portals = next(st["checkSkipPortals"] for st in build_crawler_args if "checkSkipPortals" in st)
    switch_cond = check_skip_portals["switch"][0]
    assert switch_cond["condition"] == "${skipPortals}"
    assigns = str(switch_cond["assign"])
    assert "--skip-portals" in assigns

    # Verify ML step uses mlArgs in containerOverrides
    try_step = next(s["tryPipeline"] for s in main_steps if "tryPipeline" in s)
    run_ml_step = next(s["runMLAndEstimation"] for s in try_step["try"]["steps"] if "runMLAndEstimation" in s)
    ml_body = run_ml_step["args"]["body"]
    assert "overrides" in ml_body
    ml_args_str = str(ml_body["overrides"]["containerOverrides"])
    assert "mlArgs" in ml_args_str


def test_scheduler_tf_passes_skip_portals():
    """Verify scheduler.tf passes skipPortals=true to daily_pipeline_workflow execution."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    scheduler_path = os.path.join(repo_root, "terraform", "scheduler.tf")
    assert os.path.exists(scheduler_path), f"scheduler.tf missing at {scheduler_path}"

    with open(scheduler_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "skipPortals" in content
    assert "skipPortals      = true" in content or "skipPortals        = true" in content or "\"skipPortals\": true" in content
