"""
Unit tests for Issue #664: ProxySQL Safety-Net 24-hour hourly scheduling and zone consistency.
"""
import os
import re
from unittest.mock import patch
import pytest

from package.utils import gcp_resources
from scripts import ensure_resources_stopped

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../terraform")
)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_safety_net_scheduler_cron_is_hourly():
    """基準1: realestate-safety-net-daily-${var.environment} が毎時 '0 * * * *' にスケジュールされていること"""
    scheduler_content = _read(os.path.join(TERRAFORM_DIR, "scheduler.tf"))
    block = scheduler_content.split('"crawler_safety_net_trigger"', 1)[1].split("\nresource ", 1)[0]
    schedule_match = re.search(r'schedule\s*=\s*"([^"]+)"', block)
    assert schedule_match is not None, "schedule field not found in crawler_safety_net_trigger"
    assert schedule_match.group(1) == "0 * * * *"


def test_ensure_resources_stopped_mig_fallback_uses_zone_a(monkeypatch):
    """基準2: ensure_resources_stopped.py の MIG 404 フォールバック時、デフォルトゾーンが asia-northeast1-a であること"""
    monkeypatch.delenv("PROXYSQL_ZONE", raising=False)
    monkeypatch.delenv("PROXYSQL_INSTANCE_NAME", raising=False)

    with (
        patch.object(ensure_resources_stopped, "_get_mig_info", return_value=(0, "404 Not Found", None)),
        patch.object(ensure_resources_stopped, "check_and_stop_proxysql_instance") as mock_check_inst,
    ):
        ensure_resources_stopped.check_and_stop_proxysql_mig(
            project_id="sumifu",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            fallback_to_instance=True,
        )

        mock_check_inst.assert_called_once()
        assert mock_check_inst.call_args.kwargs.get("zone") == "asia-northeast1-a"


def test_gcp_resources_proxysql_default_zone_is_zone_a(monkeypatch):
    """基準2: gcp_resources.py の ProxySQL ゾーンデフォルト値が asia-northeast1-a であること"""
    monkeypatch.delenv("PROXYSQL_ZONE", raising=False)
    monkeypatch.delenv("PROXYSQL_INSTANCE_NAME", raising=False)
    monkeypatch.setenv("IS_CLOUD", "true")

    with (
        patch.object(gcp_resources, "get_instance_status", return_value=("RUNNING", "")),
        patch.object(gcp_resources, "_execute_instance_action", return_value=True) as mock_action,
    ):
        # start
        gcp_resources.start_proxysql_instance(project_id="sumifu")
        # Since status is RUNNING, _execute_instance_action shouldn't be called, but status query was made with asia-northeast1-a
        assert gcp_resources.get_instance_status.call_args[0][1] == "asia-northeast1-a"

        # stop (when RUNNING -> calls action)
        gcp_resources.stop_proxysql_instance(project_id="sumifu")
        mock_action.assert_called_once()
        assert mock_action.call_args[0][2] == "asia-northeast1-a"


@pytest.fixture
def mock_slack():
    with patch.object(ensure_resources_stopped, "send_slack_alert") as mock:
        yield mock


def test_safety_net_skips_when_ml_pipeline_job_is_running(mock_slack):
    """基準3: MLパイプラインが実行中の場合、Safety-Net は ProxySQL の停止を安全にスキップすること"""
    mock_ml_job = ensure_resources_stopped.CloudRunExecutionInfo(
        name="projects/sumifu/locations/asia-northeast1/jobs/realestate-ml-pipeline-prod/executions/exec-ml-1",
        job_name="realestate-ml-pipeline-prod",
        elapsed_sec=300.0,
    )

    with (
        patch.object(ensure_resources_stopped, "_get_instance_info", return_value=("RUNNING", "", 1200.0)),
        patch.object(ensure_resources_stopped, "_get_active_cloud_run_executions", return_value=([mock_ml_job], "")),
        patch.object(ensure_resources_stopped, "_stop_instance") as mock_stop,
    ):
        result = ensure_resources_stopped.check_and_stop_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-a",
            instance_name="proxysql-instance-prod",
            grace_period_sec=600.0,
            timeout_threshold_sec=3600.0,
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "job_running"
        mock_stop.assert_not_called()
        mock_slack.assert_called_once()
        assert "クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました" in mock_slack.call_args[0][0]
