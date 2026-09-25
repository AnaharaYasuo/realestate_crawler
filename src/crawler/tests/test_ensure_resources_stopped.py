"""
Unit tests for ensure_resources_stopped.py (GCP Zombie Resource Prevention & Safety Net)
"""

from unittest.mock import MagicMock, patch
import pytest

try:
    from scripts.ensure_resources_stopped import (
        check_and_stop_proxysql_mig,
    )

    _MODULE_PATH = "scripts.ensure_resources_stopped"
except ImportError:
    from src.crawler.scripts.ensure_resources_stopped import (
        check_and_stop_proxysql_mig,
    )

    _MODULE_PATH = "src.crawler.scripts.ensure_resources_stopped"


@pytest.fixture
def mock_compute_client():
    mock_compute = MagicMock()
    with patch(f"{_MODULE_PATH}.compute_v1", mock_compute):
        yield mock_compute.RegionInstanceGroupManagersClient


@pytest.fixture
def mock_slack():
    with patch(f"{_MODULE_PATH}.send_slack_alert") as mock:
        yield mock


def test_proxysql_already_stopped(mock_compute_client, mock_slack):
    """When target_size == 0 and instance count == 0, no action and no alert."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance

    mock_igm = MagicMock()
    mock_igm.target_size = 0
    mock_instance.get.return_value = mock_igm

    result = check_and_stop_proxysql_mig(
        project_id="test-proj",
        region="asia-northeast1",
        mig_name="proxysql-mig-prod",
        dry_run=False,
    )

    assert result.was_leaked is False
    assert result.forced_stop is False
    mock_instance.get.assert_called_once_with(
        project="test-proj",
        region="asia-northeast1",
        instance_group_manager="proxysql-mig-prod",
        timeout=10.0,
    )
    mock_instance.resize.assert_not_called()
    mock_slack.assert_not_called()


def test_proxysql_leaked_triggers_forced_stop_and_alert(
    mock_compute_client, mock_slack
):
    """When target_size > 0 without autoscaler, resize(size=0) is called and Slack warning is emitted."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance

    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    result = check_and_stop_proxysql_mig(
        project_id="test-proj",
        region="asia-northeast1",
        mig_name="proxysql-mig-prod",
        dry_run=False,
    )

    assert result.was_leaked is True
    assert result.forced_stop is True
    assert result.leaked_size == 2
    mock_instance.resize.assert_called_once_with(
        project="test-proj",
        region="asia-northeast1",
        instance_group_manager="proxysql-mig-prod",
        size=0,
        timeout=10.0,
    )
    mock_slack.assert_called_once()
    assert "ProxySQL" in mock_slack.call_args[0][0]


def test_proxysql_leaked_with_autoscaler_scales_autoscaler_to_zero(
    mock_compute_client, mock_slack
):
    """When target_size > 0 with autoscaler, autoscaler replicas are set to 0."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance

    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(
        autoscaler="https://www.googleapis.com/compute/v1/projects/test-proj/regions/asia-northeast1/autoscalers/proxysql-autoscaler-prod"
    )
    mock_instance.get.return_value = mock_igm

    mock_autoscaler_client_cls = MagicMock()
    mock_auto_instance = MagicMock()
    mock_autoscaler_client_cls.return_value = mock_auto_instance
    mock_req_cls = MagicMock(side_effect=lambda **kw: MagicMock(**kw))

    with (
        patch(
            f"{_MODULE_PATH}.compute_v1.RegionAutoscalersClient",
            mock_autoscaler_client_cls,
            create=True,
        ),
        patch(
            f"{_MODULE_PATH}.compute_v1.PatchRegionAutoscalerRequest",
            mock_req_cls,
            create=True,
        ),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is True
        assert result.leaked_size == 2
        mock_auto_instance.patch.assert_called_once()
        patch_kwargs = mock_auto_instance.patch.call_args[1]
        req = patch_kwargs.get("request")
        if req is not None:
            assert req.autoscaler == "proxysql-autoscaler-prod"
        mock_slack.assert_called_once()


def test_proxysql_leaked_dry_run(mock_compute_client, mock_slack):
    """When dry_run=True, detects leak but does not call resize."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance

    mock_igm = MagicMock()
    mock_igm.target_size = 1
    mock_instance.get.return_value = mock_igm

    result = check_and_stop_proxysql_mig(
        project_id="test-proj",
        region="asia-northeast1",
        mig_name="proxysql-mig-prod",
        dry_run=True,
    )

    assert result.was_leaked is True
    assert result.forced_stop is False
    mock_instance.resize.assert_not_called()
    mock_slack.assert_called_once()


def test_proxysql_api_error_triggers_critical_alert(mock_compute_client, mock_slack):
    """When API returns an error (404, auth error, etc.), a critical Slack alert is emitted and leak flagged."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_instance.get.side_effect = Exception("HTTP 404: Not Found")

    with patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value=None):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert "HTTP 404" in result.details
        mock_slack.assert_called_once()
        assert ":rotating_light:" in mock_slack.call_args[0][0]


def test_proxysql_rest_fallback_success(mock_slack):
    """When compute_v1 is None, successfully queries and resizes MIG via correct REST API endpoint."""
    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 200
    mock_resp_get.json.return_value = {
        "targetSize": 3,
        "autoscaler": "https://www.googleapis.com/compute/v1/projects/test-proj/regions/asia-northeast1/autoscalers/proxysql-autoscaler-prod",
    }

    mock_resp_patch = MagicMock()
    mock_resp_patch.status_code = 200

    with (
        patch(f"{_MODULE_PATH}.compute_v1", None),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=[]),
        patch(f"{_MODULE_PATH}.requests.get", return_value=mock_resp_get) as mock_get,
        patch(
            f"{_MODULE_PATH}.requests.patch", return_value=mock_resp_patch
        ) as mock_patch,
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is True
        assert result.leaked_size == 3
        # Assert correct REST endpoint: instanceGroupManagers (NOT regionInstanceGroupManagers)
        assert "instanceGroupManagers" in mock_get.call_args[0][0]
        assert "regionInstanceGroupManagers" not in mock_get.call_args[0][0]
        mock_patch.assert_called_once()
        assert mock_patch.call_args[0][0].endswith("/autoscalers")
        assert mock_patch.call_args[1].get("params") == {
            "autoscaler": "proxysql-autoscaler-prod"
        }
        mock_slack.assert_called_once()


def test_send_slack_alert_invokes_async_send_slack_message():
    """Verify that send_slack_alert properly executes async send_slack_message without coroutine warning."""
    called = []

    async def fake_send_slack_message(channel: str, message: str) -> bool:
        called.append((channel, message))
        return True

    try:
        from scripts.ensure_resources_stopped import send_slack_alert
    except ImportError:
        from src.crawler.scripts.ensure_resources_stopped import send_slack_alert

    with patch(f"{_MODULE_PATH}.send_slack_message", fake_send_slack_message):
        send_slack_alert("Test alert message", channel="test-channel")

    assert len(called) == 1
    assert called[0] == ("test-channel", "Test alert message")


def test_proxysql_compute_v1_error_falls_back_to_rest_api(
    mock_compute_client, mock_slack
):
    """When compute_v1 raises an exception, it falls back to REST API gracefully without false alert."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_instance.get.side_effect = TypeError(
        "RegionInstanceGroupManagersClient.get() got an unexpected keyword argument 'region_instance_group_manager'"
    )
    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 200
    mock_resp_get.json.return_value = {
        "targetSize": 0,
        "autoscaler": None,
    }

    with (
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}.requests.get", return_value=mock_resp_get) as mock_get,
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        mock_instance.get.assert_called_once()
        mock_get.assert_called_once()
        mock_slack.assert_not_called()


def test_proxysql_resize_compute_v1_error_falls_back_to_rest_api(
    mock_compute_client, mock_slack
):
    """When compute_v1 resize raises an exception, it falls back to REST API gracefully."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm
    mock_instance.resize.side_effect = TypeError(
        "RegionInstanceGroupManagersClient.resize() error"
    )

    mock_resp_post = MagicMock()
    mock_resp_post.status_code = 200

    with (
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=[]),
        patch(
            f"{_MODULE_PATH}.requests.post", return_value=mock_resp_post
        ) as mock_post,
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is True
        assert result.leaked_size == 2
        mock_instance.resize.assert_called_once()
        mock_post.assert_called_once_with(
            "https://compute.googleapis.com/compute/v1/projects/test-proj/regions/asia-northeast1/instanceGroupManagers/proxysql-mig-prod/resize?size=0",
            headers={"Authorization": "Bearer fake-token"},
            timeout=10,
        )
        mock_slack.assert_called_once()


def test_proxysql_rest_invalid_target_size_triggers_alert(mock_slack):
    """When REST response lacks targetSize or has non-int, it triggers alert instead of treating as stopped."""
    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 200
    mock_resp_get.json.return_value = {"autoscaler": None}  # missing targetSize

    with (
        patch(f"{_MODULE_PATH}.compute_v1", None),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}.requests.get", return_value=mock_resp_get),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert "missing or invalid targetSize" in result.details
        mock_slack.assert_called_once()


def test_proxysql_within_grace_period_skips_stop(mock_compute_client, mock_slack):
    """When ProxySQL MIG was launched within grace_period (e.g. 300s < 600s), stop is skipped without error."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    with patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=300.0):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "grace_period"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_not_called()


def test_proxysql_with_active_job_within_timeout_skips_stop(
    mock_compute_client, mock_slack
):
    """When Cloud Run Job is RUNNING within timeout, stop is skipped and informational Slack message is sent."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    mock_exec = MagicMock()
    mock_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-crawler-pipeline-prod/executions/exec-123"
    mock_exec.job_name = "realestate-crawler-pipeline-prod"
    mock_exec.elapsed_sec = 1800.0  # 30 mins, well within 4200s

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1850.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=[mock_exec],
        ),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            timeout_threshold_sec=4200.0,
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "job_running"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_called_once()
        assert "正常実行中" in mock_slack.call_args[0][0]


def test_proxysql_with_hung_job_exceeding_timeout_dual_kill(
    mock_compute_client, mock_slack
):
    """When Cloud Run Job is RUNNING but elapsed time exceeds timeout_threshold, both Cloud Run and ProxySQL are killed."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    mock_exec = MagicMock()
    mock_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-crawler-pipeline-prod/executions/exec-hung"
    mock_exec.job_name = "realestate-crawler-pipeline-prod"
    mock_exec.elapsed_sec = 5000.0  # exceeded 4200s

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=5100.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=[mock_exec],
        ),
        patch(
            f"{_MODULE_PATH}._cancel_cloud_run_execution", return_value=""
        ) as mock_cancel,
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            timeout_threshold_sec=4200.0,
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is True
        assert result.canceled_jobs == [mock_exec.name]
        mock_cancel.assert_called_once_with(mock_exec.name)
        mock_instance.resize.assert_called_once_with(
            project="test-proj",
            region="asia-northeast1",
            instance_group_manager="proxysql-mig-prod",
            size=0,
            timeout=10.0,
        )
        mock_slack.assert_called_once()
        assert "強制停止" in mock_slack.call_args[0][0]
        assert "Cloud Run" in mock_slack.call_args[0][0]


def test_proxysql_with_active_ml_pipeline_skips_stop(
    mock_compute_client, mock_slack
):
    """When ML pricing pipeline (realestate-ml-pipeline) is RUNNING, ProxySQL stop is safely skipped."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    mock_exec = MagicMock()
    mock_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-ml-pipeline-prod/executions/ml-exec-456"
    mock_exec.job_name = "realestate-ml-pipeline-prod"
    mock_exec.elapsed_sec = 600.0  # 10 mins into pricing bulk evaluation

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=[mock_exec],
        ),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            timeout_threshold_sec=4200.0,
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "job_running"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_called_once()
        assert "MLパイプライン正常実行中" in mock_slack.call_args[0][0] or "正常実行中" in mock_slack.call_args[0][0]


