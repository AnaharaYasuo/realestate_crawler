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
    assert "new_relic_license_key" in job_block, "new_relic_license_key secret reference must be in crawler_pipeline_job"
    assert "NEW_RELIC_APP_NAME" in job_block, "NEW_RELIC_APP_NAME must be in crawler_pipeline_job"


def test_terraform_log_sink_has_cloud_run_job_filter():
    """new_relic_log_sink in terraform/new_relic_gcp_integration.tf must stream cloud_run_job logs."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    tf_path = os.path.join(root_dir, "terraform", "new_relic_gcp_integration.tf")
    assert os.path.exists(tf_path), f"File not found: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource.type = "cloud_run_job"' in content, "resource.type = 'cloud_run_job' must be in new_relic_log_sink filter"


def test_run_pipeline_initializes_new_relic():
    """run_pipeline.py must import and invoke init_new_relic."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    script_path = os.path.join(root_dir, "src", "crawler", "scripts", "ops", "run_pipeline.py")
    assert os.path.exists(script_path), f"File not found: {script_path}"

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "init_new_relic" in content, "run_pipeline.py must import and call init_new_relic"


def test_run_all_crawlers_initializes_new_relic_and_records_metrics():
    """run_all_crawlers.py must import and call init_new_relic and record_crawler_metrics."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    script_path = os.path.join(root_dir, "src", "crawler", "scripts", "ops", "run_all_crawlers.py")
    assert os.path.exists(script_path), f"File not found: {script_path}"

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "init_new_relic" in content, "run_all_crawlers.py must import and call init_new_relic"
    assert "record_crawler_metrics" in content, "run_all_crawlers.py must record crawler metrics"
