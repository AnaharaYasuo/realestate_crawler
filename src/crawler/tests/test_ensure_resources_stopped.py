"""
Unit tests for ensure_resources_stopped.py (GCP Zombie Resource Prevention & Safety Net)
"""

from unittest.mock import MagicMock, patch
import pytest

try:
    from scripts.ensure_resources_stopped import (
        check_and_stop_proxysql_mig,
        check_and_stop_proxysql_instance,
    )

    _MODULE_PATH = "scripts.ensure_resources_stopped"
except ImportError:
    from src.crawler.scripts.ensure_resources_stopped import (
        check_and_stop_proxysql_mig,
        check_and_stop_proxysql_instance,
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

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
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
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
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

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
    ):
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
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
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
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
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


def test_proxysql_at_exact_grace_period_skips_stop(mock_compute_client, mock_slack):
    """Boundary test: When uptime exactly equals grace_period (600.0s), stop is skipped."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    with patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=600.0):
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


def test_proxysql_cloud_run_query_error_skips_stop_and_alerts(
    mock_compute_client, mock_slack
):
    """When Cloud Run API query fails, fail-safe keeps ProxySQL alive and sends an urgent Slack alert."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=([], "Cloud Run API 500 error"),
        ),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert result.skipped_reason == "api_error"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_called_once()
        assert "Cloud Run Executions取得失敗" in mock_slack.call_args[0][0]
        assert "Cloud Run API 500 error" in mock_slack.call_args[0][0]


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
            return_value=([mock_exec], None),
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


def test_proxysql_at_exact_timeout_threshold_skips_stop(
    mock_compute_client, mock_slack
):
    """Boundary test: When job elapsed time exactly equals timeout_threshold (4200.0s), it is still treated as running."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    mock_exec = MagicMock()
    mock_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-crawler-pipeline-prod/executions/exec-exact"
    mock_exec.job_name = "realestate-crawler-pipeline-prod"
    mock_exec.elapsed_sec = 4200.0  # exactly 4200s

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=4300.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=([mock_exec], None),
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
            return_value=([mock_exec], None),
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


def test_proxysql_hung_job_cancel_failure_still_stops_proxysql_and_alerts(
    mock_compute_client, mock_slack
):
    """When Cloud Run cancellation fails, ProxySQL is still stopped and an alert mentioning cancellation error is sent."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    mock_exec = MagicMock()
    mock_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-crawler-pipeline-prod/executions/exec-hung"
    mock_exec.job_name = "realestate-crawler-pipeline-prod"
    mock_exec.elapsed_sec = 5000.0

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=5100.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=([mock_exec], None),
        ),
        patch(
            f"{_MODULE_PATH}._cancel_cloud_run_execution",
            return_value="PermissionDenied: 403 Forbidden",
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

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert len(result.canceled_jobs) == 0  # Cancel failed
        mock_instance.resize.assert_called_once()
        assert mock_slack.call_count == 2
        assert "強制停止処理で一部失敗が発生しました" in mock_slack.call_args[0][0]
        assert "PermissionDenied" in mock_slack.call_args[0][0]


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
            return_value=([mock_exec], None),
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
        assert "realestate-ml-pipeline-prod" in mock_slack.call_args[0][0]


def test_parse_timestamp_to_seconds_ago():
    """Verify timestamp parsing handles ISO strings, 'Z', offsets, naive, and invalid formats."""
    from datetime import datetime, timezone, timedelta
    try:
        from scripts.ensure_resources_stopped import _parse_timestamp_to_seconds_ago
    except ImportError:
        from src.crawler.scripts.ensure_resources_stopped import _parse_timestamp_to_seconds_ago

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(seconds=3600)

    # ISO with Z
    iso_z = one_hour_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    elapsed = _parse_timestamp_to_seconds_ago(iso_z)
    assert elapsed is not None
    assert 3590 <= elapsed <= 3610

    # ISO with fractional seconds and +00:00
    iso_frac = (now - timedelta(seconds=120)).isoformat()
    elapsed_frac = _parse_timestamp_to_seconds_ago(iso_frac)
    assert elapsed_frac is not None
    assert 110 <= elapsed_frac <= 130

    # Naive timestamp string
    naive_str = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=500)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    elapsed_naive = _parse_timestamp_to_seconds_ago(naive_str)
    assert elapsed_naive is not None
    assert 490 <= elapsed_naive <= 510

    # Invalid timestamp returns None (fail-safe)
    assert _parse_timestamp_to_seconds_ago("invalid-timestamp") is None
    assert _parse_timestamp_to_seconds_ago(None) is None
    assert _parse_timestamp_to_seconds_ago(12345) is None


def test_stop_autoscaler_failure_cases():
    """Verify _stop_autoscaler handles token missing and REST API errors."""
    try:
        from scripts.ensure_resources_stopped import _stop_autoscaler, ERR_NO_COMPUTE_CLIENT
    except ImportError:
        from src.crawler.scripts.ensure_resources_stopped import _stop_autoscaler, ERR_NO_COMPUTE_CLIENT

    # 1. No token returns ERR_NO_COMPUTE_CLIENT
    with (
        patch(f"{_MODULE_PATH}.compute_v1", None),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value=None),
    ):
        err = _stop_autoscaler("test-proj", "asia-northeast1", "auto-1")
        assert err == ERR_NO_COMPUTE_CLIENT

    # 2. REST API error returns HTTP status string
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    with (
        patch(f"{_MODULE_PATH}.compute_v1", None),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}.requests.patch", return_value=mock_resp),
    ):
        err = _stop_autoscaler("test-proj", "asia-northeast1", "auto-1")
        assert "HTTP 503: Service Unavailable" in err


def test_proxysql_stop_failure_records_error_and_alerts(mock_compute_client, mock_slack):
    """When stop_err occurs during orphaned ProxySQL stop, forced_stop is False and details are set."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], None)),
        patch(f"{_MODULE_PATH}._resize_mig_to_zero", return_value="Failed to resize"),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert result.details == "Failed to resize"
        assert mock_slack.call_count == 2
        assert "強制停止に失敗しました" in mock_slack.call_args[0][0]


def test_main_cli_execution():
    """Verify main() entrypoint executes successfully and returns 0."""
    try:
        from scripts.ensure_resources_stopped import main
    except ImportError:
        from src.crawler.scripts.ensure_resources_stopped import main

    with (
        patch("sys.argv", ["ensure_resources_stopped.py", "--dry-run"]),
        patch(f"{_MODULE_PATH}.check_and_stop_proxysql_mig") as mock_check,
    ):
        mock_res = MagicMock()
        mock_res.was_leaked = False
        mock_res.forced_stop = False
        mock_res.leaked_size = 0
        mock_res.details = ""
        mock_res.skipped_reason = ""
        mock_res.canceled_jobs = []
        mock_check.return_value = mock_res

        exit_code = main()
        assert exit_code == 0
        mock_check.assert_called_once()


def test_proxysql_uptime_unknown_skips_stop(mock_compute_client, mock_slack):
    """When MIG uptime is None (cannot be determined), stop is skipped for safety."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    with patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=None):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )

        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "uptime_unknown"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_not_called()


def test_proxysql_hung_job_cancelled_but_healthy_job_prevents_proxysql_stop(
    mock_compute_client, mock_slack
):
    """When one job is hung (>4200s) but another is healthy (within timeout), hung job is cancelled but ProxySQL MIG stop is skipped."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    hung_exec = MagicMock()
    hung_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-crawler-pipeline-prod/executions/hung-1"
    hung_exec.job_name = "realestate-crawler-pipeline-prod"
    hung_exec.elapsed_sec = 5000.0

    healthy_exec = MagicMock()
    healthy_exec.name = "projects/test-proj/locations/asia-northeast1/jobs/realestate-ml-pipeline-prod/executions/healthy-1"
    healthy_exec.job_name = "realestate-ml-pipeline-prod"
    healthy_exec.elapsed_sec = 800.0

    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=5100.0),
        patch(
            f"{_MODULE_PATH}._get_active_cloud_run_executions",
            return_value=([hung_exec, healthy_exec], None),
        ),
        patch(f"{_MODULE_PATH}._cancel_cloud_run_execution", return_value="") as mock_cancel,
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
        assert result.skipped_reason == "healthy_jobs_still_running"
        assert result.canceled_jobs == [hung_exec.name]
        mock_cancel.assert_called_once_with(hung_exec.name)
        mock_instance.resize.assert_not_called()
        mock_slack.assert_called_once()
        assert "ジョブ異常超過検知" in mock_slack.call_args[0][0]


def test_get_active_cloud_run_executions_direct_failure_paths(mock_compute_client, mock_slack):
    """Directly test run_v2 exception and REST 403 failure in _get_active_cloud_run_executions and check_and_stop_proxysql_mig."""
    try:
        from scripts.ensure_resources_stopped import _get_active_cloud_run_executions
    except ImportError:
        from src.crawler.scripts.ensure_resources_stopped import _get_active_cloud_run_executions

    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance
    mock_igm = MagicMock()
    mock_igm.target_size = 2
    mock_igm.status = MagicMock(autoscaler=None)
    mock_instance.get.return_value = mock_igm

    # 1. run_v2 raises exception and REST returns 403 Forbidden
    mock_run_v2 = MagicMock()
    mock_run_client = MagicMock()
    mock_run_client.list_executions.side_effect = RuntimeError("run_v2 gRPC transport broken")
    mock_run_v2.ExecutionsClient.return_value = mock_run_client

    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    mock_resp_403.text = "Permission Denied"

    with (
        patch(f"{_MODULE_PATH}.run_v2", mock_run_v2),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}.requests.get", return_value=mock_resp_403),
    ):
        active, err = _get_active_cloud_run_executions("test-proj", "asia-northeast1", ("job-",))
        assert active == []
        assert "HTTP 403" in err

    # 2. Verify that this API error passes through check_and_stop_proxysql_mig, skips stopping, and alerts
    with (
        patch(f"{_MODULE_PATH}._get_mig_uptime_seconds", return_value=1200.0),
        patch(f"{_MODULE_PATH}.run_v2", mock_run_v2),
        patch(f"{_MODULE_PATH}._get_gcp_access_token", return_value="fake-token"),
        patch(f"{_MODULE_PATH}.requests.get", return_value=mock_resp_403),
    ):
        result = check_and_stop_proxysql_mig(
            project_id="test-proj",
            region="asia-northeast1",
            mig_name="proxysql-mig-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )

        assert result.was_leaked is True
        assert result.forced_stop is False
        assert result.skipped_reason == "api_error"
        mock_instance.resize.assert_not_called()
        mock_slack.assert_called_once()
        assert "【緊急】Cloud Run Executions取得失敗" in mock_slack.call_args[0][0]


def test_proxysql_instance_already_stopped(mock_slack):
    """When instance is TERMINATED or STOPPED, no action and no alert."""
    with patch(f"{_MODULE_PATH}._get_instance_info", return_value=("TERMINATED", "", None)):
        result = check_and_stop_proxysql_instance(
            project_id="test-proj",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            dry_run=False,
        )
        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "stopped"
        mock_slack.assert_not_called()


def test_proxysql_instance_within_grace_period(mock_slack):
    """When instance is RUNNING but within grace_period (e.g. 300s <= 600s), stop is skipped."""
    with patch(f"{_MODULE_PATH}._get_instance_info", return_value=("RUNNING", "", 300.0)):
        result = check_and_stop_proxysql_instance(
            project_id="test-proj",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )
        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "grace_period"
        mock_slack.assert_not_called()


def test_proxysql_instance_with_active_job_within_timeout_skips_stop(mock_slack):
    """When instance is RUNNING and active job is within timeout, stop is skipped."""
    from scripts.ensure_resources_stopped import CloudRunExecutionInfo

    mock_job = CloudRunExecutionInfo(name="exec-1", job_name="crawler-job", elapsed_sec=120.0)

    with (
        patch(f"{_MODULE_PATH}._get_instance_info", return_value=("RUNNING", "", 1200.0)),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([mock_job], "")),
    ):
        result = check_and_stop_proxysql_instance(
            project_id="test-proj",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )
        assert result.was_leaked is False
        assert result.forced_stop is False
        assert result.skipped_reason == "job_running"
        mock_slack.assert_called_once()
        assert "正常実行中のためProxySQL停止をスキップしました" in mock_slack.call_args[0][0]


def test_proxysql_instance_orphaned_stopped(mock_slack):
    """When instance is RUNNING past grace period and no jobs are active, instance is stopped."""
    with (
        patch(f"{_MODULE_PATH}._get_instance_info", return_value=("RUNNING", "", 1200.0)),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([], "")),
        patch(f"{_MODULE_PATH}._stop_instance", return_value="") as mock_stop,
    ):
        result = check_and_stop_proxysql_instance(
            project_id="test-proj",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            grace_period_sec=600.0,
            dry_run=False,
        )
        assert result.was_leaked is True
        assert result.forced_stop is True
        mock_stop.assert_called_once_with("test-proj", "asia-northeast1-b", "proxysql-instance-prod")
        assert mock_slack.call_count == 1
        assert "ProxySQL停止漏れ検知" in mock_slack.call_args[0][0]


def test_proxysql_instance_hung_job_dual_kill(mock_slack):
    """When Cloud Run job exceeds timeout, cancels job and stops instance."""
    from scripts.ensure_resources_stopped import CloudRunExecutionInfo

    mock_hung = CloudRunExecutionInfo(name="exec-hung", job_name="crawler-job", elapsed_sec=5000.0)

    with (
        patch(f"{_MODULE_PATH}._get_instance_info", return_value=("RUNNING", "", 5000.0)),
        patch(f"{_MODULE_PATH}._get_active_cloud_run_executions", return_value=([mock_hung], "")),
        patch(f"{_MODULE_PATH}._cancel_cloud_run_execution", return_value="") as mock_cancel,
        patch(f"{_MODULE_PATH}._stop_instance", return_value="") as mock_stop,
    ):
        result = check_and_stop_proxysql_instance(
            project_id="test-proj",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            grace_period_sec=600.0,
            timeout_threshold_sec=4200.0,
            dry_run=False,
        )
        assert result.was_leaked is True
        assert result.forced_stop is True
        mock_cancel.assert_called_once_with("exec-hung")
        mock_stop.assert_called_once_with("test-proj", "asia-northeast1-b", "proxysql-instance-prod")
        assert mock_slack.call_count == 1
        assert "ジョブ異常超過検知" in mock_slack.call_args[0][0]






