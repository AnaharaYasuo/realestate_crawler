import os
import re


def test_terraform_cloud_run_job_has_new_relic_config():
    """crawler_pipeline_job in terraform/cloud_run_job.tf must define NEW_RELIC_LICENSE_KEY."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    tf_path = os.path.join(root_dir, "terraform", "cloud_run_job.tf")
    assert os.path.exists(tf_path), f"File not found: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find crawler_pipeline_job block
    match = re.search(r'resource\s+"google_cloud_run_v2_job"\s+"crawler_pipeline_job"\s+\{([\s\S]*?)\nresource\s+"google_cloud_run_v2_job"', content)
    assert match is not None, "crawler_pipeline_job resource not found in cloud_run_job.tf"
    job_block = match.group(1)

    assert "NEW_RELIC_LICENSE_KEY" in job_block, "NEW_RELIC_LICENSE_KEY must be in crawler_pipeline_job"
    assert "google_secret_manager_secret.new_relic_license_key.secret_id" in job_block, (
        "NEW_RELIC_LICENSE_KEY must map to google_secret_manager_secret.new_relic_license_key.secret_id"
    )
    assert 'value = "realestate-crawler-pipeline-${var.environment}"' in job_block, (
        "NEW_RELIC_APP_NAME must use environment variable interpolation"
    )
    assert 'value = "true"' in job_block, "NEW_RELIC_DISTRIBUTED_TRACING_ENABLED must be true"


def test_terraform_log_sink_has_cloud_run_job_filter():
    """new_relic_log_sink in terraform/new_relic_gcp_integration.tf must stream cloud_run_job logs."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    tf_path = os.path.join(root_dir, "terraform", "new_relic_gcp_integration.tf")
    assert os.path.exists(tf_path), f"File not found: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'resource\s+"google_logging_project_sink"\s+"new_relic_log_sink"\s+\{([\s\S]*?)\n\}', content)
    assert match is not None, "new_relic_log_sink resource not found"
    sink_block = match.group(1)
    assert 'resource.type = "cloud_run_job"' in sink_block, "resource.type = 'cloud_run_job' must be in new_relic_log_sink filter"


def test_run_pipeline_initializes_new_relic():
    """run_pipeline.py must import and invoke init_new_relic in main flow."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    script_path = os.path.join(root_dir, "src", "crawler", "scripts", "ops", "run_pipeline.py")
    assert os.path.exists(script_path), f"File not found: {script_path}"

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    import ast
    tree = ast.parse(content)
    # Verify init_new_relic is imported
    imported_names = [
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert "init_new_relic" in imported_names, "init_new_relic must be imported in run_pipeline.py"

    # Verify init_new_relic is called
    call_names = [
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "init_new_relic" in call_names, "init_new_relic() must be called in run_pipeline.py"


def test_run_all_crawlers_initializes_new_relic_and_records_metrics():
    """run_all_crawlers.py must import and call init_new_relic and record_crawler_metrics across exit paths."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    script_path = os.path.join(root_dir, "src", "crawler", "scripts", "ops", "run_all_crawlers.py")
    assert os.path.exists(script_path), f"File not found: {script_path}"

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    import ast
    tree = ast.parse(content)
    imported_names = [
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert "init_new_relic" in imported_names, "init_new_relic must be imported"
    assert "record_crawler_metrics" in imported_names, "record_crawler_metrics must be imported"

    # Verify calls to record_crawler_metrics exist in the AST (success, timeout, startup failure)
    metric_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "record_crawler_metrics"
    ]
    assert len(metric_calls) >= 3, f"Expected at least 3 record_crawler_metrics calls (success, timeout, error), found {len(metric_calls)}"
