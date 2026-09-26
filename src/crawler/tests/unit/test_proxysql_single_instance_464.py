"""
Unit tests for ProxySQL single GCE instance transition (Issue #464).
Verifies:
1. run_pipeline.py skips Autoscaler patch when single instance is configured.
2. ensure_resources_stopped.py uses single instance and handles MIG 404 without false emergency alert.
3. terraform and deploy-production configuration set PROXYSQL_INSTANCE_NAME.
"""

import os
import sys
from unittest.mock import patch


_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401

        break
    _cur = _parent

from package.utils import gcp_resources
from scripts import ensure_resources_stopped
from scripts.ops import run_pipeline

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../terraform")
)
WORKFLOWS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../.github/workflows")
)


def test_run_pipeline_startup_skips_autoscaler_in_single_instance_mode(monkeypatch):
    """When PROXYSQL_INSTANCE_NAME is set, _execute_startup_resources must skip patch_proxysql_autoscaler."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")

    with (
        patch.object(
            run_pipeline, "check_cloud_sql_status", return_value=(True, "RUNNABLE")
        ),
        patch.object(run_pipeline, "patch_proxysql_autoscaler") as mock_patch_auto,
        patch.object(
            run_pipeline, "scale_proxysql_mig", return_value=True
        ) as mock_scale,
        patch.object(
            run_pipeline, "wait_for_proxysql_health", return_value=True
        ) as mock_health,
    ):
        run_pipeline._execute_startup_resources(is_coordinator=True)

        # patch_proxysql_autoscaler should NOT be called in single instance mode
        mock_patch_auto.assert_not_called()
        # scale_proxysql_mig and wait_for_proxysql_health must be called
        mock_scale.assert_called_once_with(target_size=1)
        mock_health.assert_called_once()


def test_run_pipeline_inline_teardown_skips_autoscaler_in_single_instance_mode(
    monkeypatch,
):
    """When PROXYSQL_INSTANCE_NAME is set, _inline_stop_proxysql must skip patch_proxysql_autoscaler."""
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")

    with (
        patch.object(run_pipeline, "patch_proxysql_autoscaler") as mock_patch_auto,
        patch.object(
            run_pipeline, "scale_proxysql_mig", return_value=True
        ) as mock_scale,
    ):
        run_pipeline._inline_stop_proxysql()

        mock_patch_auto.assert_not_called()
        mock_scale.assert_called_once_with(target_size=0)


def test_patch_proxysql_autoscaler_safe_noop_when_single_instance(monkeypatch):
    """When PROXYSQL_INSTANCE_NAME is set in cloud mode, patch_proxysql_autoscaler returns True safely without updating Autoscaler."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")

    with (
        patch.object(gcp_resources, "_patch_autoscaler_via_compute_v1") as mock_compute,
        patch.object(gcp_resources, "_patch_autoscaler_via_rest") as mock_rest,
    ):
        res = gcp_resources.patch_proxysql_autoscaler(min_replicas=1, max_replicas=2)
        assert res is True
        mock_compute.assert_not_called()
        mock_rest.assert_not_called()


def test_ensure_resources_stopped_uses_instance_name_from_env_default(monkeypatch):
    """When PROXYSQL_INSTANCE_NAME is in env, ensure_resources_stopped.main delegates to instance check."""
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")

    with (
        patch.object(
            ensure_resources_stopped,
            "check_and_stop_proxysql_instance",
            return_value=ensure_resources_stopped.ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=0,
                skipped_reason="stopped",
            ),
        ) as mock_check_inst,
        patch.object(
            ensure_resources_stopped, "check_and_stop_proxysql_mig"
        ) as mock_check_mig,
        patch.object(sys, "argv", ["ensure_resources_stopped.py"]),
    ):
        rc = ensure_resources_stopped.main()
        assert rc == 0
        mock_check_inst.assert_called_once()
        mock_check_mig.assert_not_called()


def test_ensure_resources_stopped_mig_404_falls_back_to_instance_without_alert(
    monkeypatch,
):
    """If check_and_stop_proxysql_mig receives 404, it falls back to single instance instead of raising emergency alert."""
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("ENVIRONMENT", "prod")

    mig_404_err = "404 GET ... The resource '.../instanceGroupManagers/proxysql-mig-prod' was not found"

    with (
        patch.object(
            ensure_resources_stopped,
            "_get_mig_info",
            return_value=(0, mig_404_err, None),
        ),
        patch.object(
            ensure_resources_stopped,
            "check_and_stop_proxysql_instance",
            return_value=ensure_resources_stopped.ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=0,
                skipped_reason="stopped",
            ),
        ) as mock_check_inst,
        patch.object(ensure_resources_stopped, "send_slack_alert") as mock_alert,
    ):
        result = ensure_resources_stopped.check_and_stop_proxysql_mig(
            project_id="test-project",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            fallback_to_instance=True,
        )

        assert result.was_leaked is False
        mock_check_inst.assert_called_once()
        assert mock_check_inst.call_args.kwargs.get("zone") == "asia-northeast1-b"
        # False emergency alert must NOT be sent
        mock_alert.assert_not_called()


def test_terraform_and_workflows_config():
    """Verify terraform and deploy-production.yml contain PROXYSQL_INSTANCE_NAME and PROXYSQL_ZONE separately."""
    job_tf = os.path.join(TERRAFORM_DIR, "cloud_run_job.tf")
    with open(job_tf, "r", encoding="utf-8") as f:
        job_content = f.read()

    # Split into job blocks to independently verify crawler_pipeline_job and resource_safety_net_job
    crawler_block = job_content.split(
        'resource "google_cloud_run_v2_job" "db_migrate_job"'
    )[0]
    safety_net_block = job_content.split(
        'resource "google_cloud_run_v2_job" "resource_safety_net_job"'
    )[1].split('resource "google_cloud_run_v2_job" "crawler_dispatcher_job"')[0]

    assert 'name  = "PROXYSQL_INSTANCE_NAME"' in crawler_block, (
        "crawler_pipeline_job must set PROXYSQL_INSTANCE_NAME"
    )
    assert 'name  = "PROXYSQL_ZONE"' in crawler_block, (
        "crawler_pipeline_job must set PROXYSQL_ZONE"
    )

    assert 'name  = "PROXYSQL_INSTANCE_NAME"' in safety_net_block, (
        "resource_safety_net_job must set PROXYSQL_INSTANCE_NAME"
    )
    assert 'name  = "PROXYSQL_ZONE"' in safety_net_block, (
        "resource_safety_net_job must set PROXYSQL_ZONE"
    )

    deploy_yml = os.path.join(WORKFLOWS_DIR, "deploy-production.yml")
    with open(deploy_yml, "r", encoding="utf-8") as f:
        deploy_content = f.read()

    assert "--instance-name=proxysql-instance-prod" in deploy_content, (
        "deploy-production.yml must pass --instance-name"
    )
