# -*- coding: utf-8 -*-
"""Unit tests for gcp_resources utility module (ProxySQL MIG, GCE, Auth)."""

from unittest.mock import MagicMock, patch

from package.utils import gcp_resources


def test_get_gcp_access_token_via_google_auth():
    """Verify get_gcp_access_token succeeds via google.auth."""
    mock_creds = MagicMock()
    mock_creds.token = "auth-token-123"

    with patch.object(gcp_resources, "google") as mock_google:
        mock_google.auth.default.return_value = (mock_creds, "test-proj")
        token = gcp_resources.get_gcp_access_token()
        assert token == "auth-token-123"
        mock_creds.refresh.assert_called_once()


def test_get_gcp_access_token_via_metadata_server():
    """Verify get_gcp_access_token falls back to metadata server if google.auth fails."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "metadata-token-456"}

    with (
        patch.object(gcp_resources, "google", None),
        patch("requests.get", return_value=mock_resp) as mock_get,
    ):
        token = gcp_resources.get_gcp_access_token()
        assert token == "metadata-token-456"
        mock_get.assert_called_once()


def test_get_gcp_access_token_returns_none_on_all_failures():
    """Verify get_gcp_access_token returns None if both auth and metadata fail."""
    with (
        patch.object(gcp_resources, "google", None),
        patch("requests.get", side_effect=Exception("Metadata server error")),
    ):
        token = gcp_resources.get_gcp_access_token()
        assert token is None


def test_scale_proxysql_mig_dry_run_or_local():
    """Verify scale_proxysql_mig returns True immediately on dry_run or local environment."""
    # dry_run = True
    assert gcp_resources.scale_proxysql_mig(target_size=1, dry_run=True) is True

    # local env (no IS_CLOUD, K_SERVICE, CLOUD_RUN_JOB)
    with patch.dict("os.environ", {}, clear=True):
        assert gcp_resources.scale_proxysql_mig(target_size=1, dry_run=False) is True


def test_scale_proxysql_mig_via_compute_v1(monkeypatch):
    """Verify scale_proxysql_mig uses compute_v1 when available."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    mock_client = MagicMock()
    mock_op = MagicMock()
    mock_op.name = "op-123"
    mock_client.resize.return_value = mock_op

    mock_compute_module = MagicMock()
    mock_compute_module.RegionInstanceGroupManagersClient.return_value = mock_client

    res = gcp_resources.scale_proxysql_mig(
        target_size=1,
        compute_module=mock_compute_module,
    )
    assert res is True
    mock_client.resize.assert_called_once_with(
        project="sumifu",
        region="asia-northeast1",
        instance_group_manager="proxysql-mig-prod",
        size=1,
    )


def test_scale_proxysql_mig_via_rest_api_fallback(monkeypatch):
    """Verify scale_proxysql_mig falls back to REST API when compute_v1 fails."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"targetSize": 0}

    with (
        patch("requests.get", return_value=mock_resp),
        patch("requests.post", return_value=mock_resp) as mock_post,
    ):
        res = gcp_resources.scale_proxysql_mig(
            target_size=0,
            compute_module=None,
            get_token_callback=lambda: "bearer-token-789",
        )
        assert res is True
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "instanceGroupManagers/proxysql-mig-prod/resize?size=0" in url


def test_scale_proxysql_mig_falls_back_when_compute_v1_raises(monkeypatch):
    """Verify scale_proxysql_mig falls back to REST API when compute_v1 raises an exception."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    mock_compute = MagicMock()
    mock_compute.RegionInstanceGroupManagersClient.return_value.resize.side_effect = (
        Exception("Compute API error")
    )
    mock_resp = MagicMock(status_code=200)

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = gcp_resources.scale_proxysql_mig(
            target_size=0,
            compute_module=mock_compute,
            get_token_callback=lambda: "tok",
        )
        assert res is True

    mock_compute.RegionInstanceGroupManagersClient.return_value.resize.assert_called_once()
    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "instanceGroupManagers/proxysql-mig-prod/resize?size=0" in url


def test_scale_proxysql_mig_fails_when_all_fail(monkeypatch):
    """Verify scale_proxysql_mig returns False when compute_v1 and REST API fail."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")

    with patch("requests.post", side_effect=Exception("HTTP error")):
        res = gcp_resources.scale_proxysql_mig(
            target_size=1,
            compute_module=None,
            get_token_callback=lambda: "token",
        )
        assert res is False


def test_wait_for_proxysql_health_local_returns_true():
    """Verify wait_for_proxysql_health returns True immediately in local/test environment."""
    with patch.dict("os.environ", {}, clear=True):
        assert gcp_resources.wait_for_proxysql_health() is True


def test_wait_for_proxysql_health_cloud_success(monkeypatch):
    """Verify wait_for_proxysql_health succeeds when socket connects."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("DB_HOST", "10.0.0.2")
    monkeypatch.setenv("DB_PORT", "6033")

    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        assert gcp_resources.wait_for_proxysql_health(timeout_sec=5) is True
        mock_conn.assert_called_once_with(("10.0.0.2", 6033), timeout=2.0)


def test_wait_for_proxysql_health_cloud_timeout(monkeypatch):
    """Verify wait_for_proxysql_health returns False when socket connection times out."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("DB_HOST", "10.0.0.2")
    monkeypatch.setenv("DB_PORT", "6033")

    with patch("socket.create_connection", side_effect=OSError("Connection refused")), patch("time.sleep"):
        assert gcp_resources.wait_for_proxysql_health(timeout_sec=1) is False


def test_patch_proxysql_autoscaler_local_returns_true():
    """Verify patch_proxysql_autoscaler returns True immediately in local/test environment."""
    with patch.dict("os.environ", {}, clear=True):
        assert gcp_resources.patch_proxysql_autoscaler(min_replicas=1, max_replicas=2) is True


def test_patch_proxysql_autoscaler_compute_v1_success(monkeypatch):
    """Verify patch_proxysql_autoscaler patches via RegionAutoscalersClient in cloud."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")

    mock_client = MagicMock()
    mock_compute = MagicMock()
    mock_compute.RegionAutoscalersClient.return_value = mock_client
    mock_compute.PatchRegionAutoscalerRequest = MagicMock()
    mock_compute.AutoscalingPolicy = MagicMock()
    mock_compute.Autoscaler = MagicMock()

    res = gcp_resources.patch_proxysql_autoscaler(
        min_replicas=1,
        max_replicas=2,
        compute_module=mock_compute,
    )
    assert res is True
    mock_compute.AutoscalingPolicy.assert_called_once_with(min_num_replicas=1, max_num_replicas=2)
    mock_client.patch.assert_called_once()
    req_kwargs = mock_compute.PatchRegionAutoscalerRequest.call_args[1]
    assert req_kwargs["project"] == "test-project"
    assert req_kwargs["region"] == "asia-northeast1"
    assert req_kwargs["autoscaler"] == "proxysql-autoscaler-prod"


def test_patch_proxysql_autoscaler_rest_fallback(monkeypatch):
    """Verify patch_proxysql_autoscaler falls back to REST API when compute_v1 unavailable."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.patch", return_value=mock_resp) as mock_patch:
        res = gcp_resources.patch_proxysql_autoscaler(
            min_replicas=1,
            max_replicas=2,
            compute_module=None,
            get_token_callback=lambda: "mock-token",
        )
        assert res is True
        mock_patch.assert_called_once()
        called_url = mock_patch.call_args[0][0]
        called_kwargs = mock_patch.call_args[1]
        assert "projects/test-project/regions/asia-northeast1/autoscalers" in called_url
        assert called_kwargs["params"] == {"autoscaler": "proxysql-autoscaler-prod"}
        assert called_kwargs["json"] == {
            "autoscalingPolicy": {
                "minNumReplicas": 1,
                "maxNumReplicas": 2,
            }
        }


def test_patch_proxysql_autoscaler_fails_when_all_fail(monkeypatch):
    """Verify patch_proxysql_autoscaler returns False when both compute_v1 and REST API fail."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "test-project")

    with patch("requests.patch", side_effect=Exception("HTTP error")):
        res = gcp_resources.patch_proxysql_autoscaler(
            min_replicas=1,
            max_replicas=2,
            compute_module=None,
            get_token_callback=lambda: "token",
        )
        assert res is False


def test_scale_proxysql_mig_autoscaled_detected_scales_autoscaler(monkeypatch):
    """Verify scale_proxysql_mig detects attached autoscaler and scales autoscaler instead of resize."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    mock_client = MagicMock()
    mock_compute = MagicMock()
    mock_compute.RegionInstanceGroupManagersClient.return_value = mock_client

    with (
        patch.object(gcp_resources, "get_mig_info", return_value=(0, "", "proxysql-autoscaler-prod")),
        patch.object(gcp_resources, "patch_proxysql_autoscaler", return_value=True) as mock_patch_auto,
    ):
        res = gcp_resources.scale_proxysql_mig(
            target_size=1,
            compute_module=mock_compute,
        )
        assert res is True
        mock_patch_auto.assert_called_once_with(
            min_replicas=1,
            max_replicas=2,
            project_id="sumifu",
            region="asia-northeast1",
            autoscaler_name="proxysql-autoscaler-prod",
            dry_run=False,
            compute_module=mock_compute,
            get_token_callback=None,
        )
        # client.resize must NOT be called when autoscaler is detected
        mock_client.resize.assert_not_called()


def test_check_cloud_sql_status_runnable(monkeypatch):
    """Verify check_cloud_sql_status returns (True, 'RUNNABLE') when instance is RUNNABLE."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"state": "RUNNABLE", "settings": {"activationPolicy": "ALWAYS"}}

    with (
        patch.object(gcp_resources, "get_gcp_access_token", return_value="token-123"),
        patch("requests.get", return_value=mock_resp),
    ):
        ok, state = gcp_resources.check_cloud_sql_status()
        assert ok is True
        assert state == "RUNNABLE"


def test_check_cloud_sql_status_stopped(monkeypatch):
    """Verify check_cloud_sql_status returns (False, 'STOPPED') when instance is STOPPED."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"state": "STOPPED", "settings": {"activationPolicy": "NEVER"}}

    with (
        patch.object(gcp_resources, "get_gcp_access_token", return_value="token-123"),
        patch("requests.get", return_value=mock_resp),
    ):
        ok, state = gcp_resources.check_cloud_sql_status()
        assert ok is False
        assert state == "STOPPED"


def test_get_gcp_access_token_custom_scope():
    """Verify get_gcp_access_token uses custom scopes when provided."""
    mock_creds = MagicMock()
    mock_creds.token = "custom-token"
    with patch.object(gcp_resources, "google") as mock_google:
        mock_google.auth.default.return_value = (mock_creds, "test-proj")
        token = gcp_resources.get_gcp_access_token(scopes=["custom-scope"])
        assert token == "custom-token"
        mock_google.auth.default.assert_called_once_with(scopes=["custom-scope"])


def test_resize_mig_via_rest_no_token():
    """Verify _resize_mig_via_rest returns False when token is None."""
    assert gcp_resources._resize_mig_via_rest("proj", "reg", "mig", 1, None) is False


def test_resize_mig_via_rest_http_error():
    """Verify _resize_mig_via_rest returns False when REST API returns error."""
    mock_resp = MagicMock(status_code=500, text="Internal Error")
    with patch("requests.post", return_value=mock_resp):
        assert gcp_resources._resize_mig_via_rest("proj", "reg", "mig", 1, "tok") is False


def test_scale_proxysql_mig_fails_when_mig_inspection_errors(monkeypatch):
    """Verify scale_proxysql_mig returns False when get_mig_info encounters an error."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    with patch.object(gcp_resources, "get_mig_info", return_value=(-1, "API check failed", None)):
        res = gcp_resources.scale_proxysql_mig(target_size=1)
        assert res is False


def test_check_cloud_sql_status_404_prefix_match_success(monkeypatch):
    """Verify check_cloud_sql_status falls back to instances list and matches prefix on 404."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("CLOUDSQL_INSTANCE_NAME", "realestate-mysql-prod")

    mock_404 = MagicMock(status_code=404)
    mock_list_200 = MagicMock(
        status_code=200,
        json=lambda: {
            "items": [
                {
                    "name": "realestate-mysql-prod-748272a1",
                    "state": "RUNNABLE",
                    "settings": {"activationPolicy": "ALWAYS"},
                }
            ]
        },
    )

    with patch("requests.get", side_effect=[mock_404, mock_list_200]) as mock_get, \
         patch.object(gcp_resources, "get_gcp_access_token", return_value="fake-token"):
        ok, state = gcp_resources.check_cloud_sql_status()
        assert ok is True
        assert state == "RUNNABLE"
        assert [call.args[0] for call in mock_get.call_args_list] == [
            "https://sqladmin.googleapis.com/v1/projects/sumifu/instances/realestate-mysql-prod",
            "https://sqladmin.googleapis.com/v1/projects/sumifu/instances",
        ]


def test_check_cloud_sql_status_404_prefix_match_not_found(monkeypatch):
    """Verify check_cloud_sql_status returns False and HTTP 404 when no matching prefix instance exists."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("CLOUDSQL_INSTANCE_NAME", "realestate-mysql-prod")

    mock_404 = MagicMock(status_code=404)
    mock_list_empty = MagicMock(
        status_code=200,
        json=lambda: {"items": [{"name": "other-db-instance", "state": "RUNNABLE"}]},
    )

    with patch("requests.get", side_effect=[mock_404, mock_list_empty]) as mock_get, \
         patch.object(gcp_resources, "get_gcp_access_token", return_value="fake-token"):
        ok, state = gcp_resources.check_cloud_sql_status()
        assert ok is False
        assert state == "HTTP 404"
        assert [call.args[0] for call in mock_get.call_args_list] == [
            "https://sqladmin.googleapis.com/v1/projects/sumifu/instances/realestate-mysql-prod",
            "https://sqladmin.googleapis.com/v1/projects/sumifu/instances",
        ]


def test_check_cloud_sql_status_404_multiple_matches(monkeypatch):
    """Verify check_cloud_sql_status returns False and MULTIPLE_MATCHES when prefix is ambiguous."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("CLOUDSQL_INSTANCE_NAME", "realestate-mysql-prod")

    mock_404 = MagicMock(status_code=404)
    mock_list_multiple = MagicMock(
        status_code=200,
        json=lambda: {
            "items": [
                {"name": "realestate-mysql-prod-aaa", "state": "RUNNABLE"},
                {"name": "realestate-mysql-prod-bbb", "state": "RUNNABLE"},
            ]
        },
    )

    with patch("requests.get", side_effect=[mock_404, mock_list_multiple]), \
         patch.object(gcp_resources, "get_gcp_access_token", return_value="fake-token"):
        ok, state = gcp_resources.check_cloud_sql_status()
        assert ok is False
        assert state == "MULTIPLE_MATCHES"


def test_is_prefix_matched():
    """Verify _is_prefix_matched correctly matches exact prefix or prefix with hyphen."""
    assert gcp_resources._is_prefix_matched("prod-db", "prod-db") is True
    assert gcp_resources._is_prefix_matched("prod-db-1234", "prod-db") is True
    assert gcp_resources._is_prefix_matched("prod-db2", "prod-db") is False
    assert gcp_resources._is_prefix_matched("staging-db", "prod-db") is False


def test_evaluate_sql_instances_matches():
    """Verify _evaluate_sql_instances_matches handles 1 match, multiple matches, and 0 matches."""
    # Single match RUNNABLE
    ok, state = gcp_resources._evaluate_sql_instances_matches(
        [{"name": "prod-db-1", "state": "RUNNABLE", "settings": {"activationPolicy": "ALWAYS"}}],
        "prod-db",
    )
    assert ok is True
    assert state == "RUNNABLE"

    # Single match STOPPED
    ok, state = gcp_resources._evaluate_sql_instances_matches(
        [{"name": "prod-db-1", "state": "STOPPED", "settings": {"activationPolicy": "NEVER"}}],
        "prod-db",
    )
    assert ok is False
    assert state == "STOPPED"

    # Multiple matches
    ok, state = gcp_resources._evaluate_sql_instances_matches(
        [{"name": "prod-db-1"}, {"name": "prod-db-2"}],
        "prod-db",
    )
    assert ok is False
    assert state == "MULTIPLE_MATCHES"

    # Zero matches
    ok, state = gcp_resources._evaluate_sql_instances_matches([], "prod-db")
    assert ok is False
    assert state == "HTTP 404"


def test_fetch_cloud_sql_instances_by_prefix_pagination():
    """Verify _fetch_cloud_sql_instances_by_prefix handles pagination across multiple pages."""
    page1 = MagicMock(
        status_code=200,
        json=lambda: {
            "items": [{"name": "db-inst-1"}, {"name": "other-1"}],
            "nextPageToken": "token-page-2",
        },
    )
    page2 = MagicMock(
        status_code=200,
        json=lambda: {
            "items": [{"name": "db-inst-2"}],
        },
    )

    with patch("requests.get", side_effect=[page1, page2]) as mock_get:
        matches, err = gcp_resources._fetch_cloud_sql_instances_by_prefix("proj", "db-inst", "token")
        assert err is None
        assert len(matches) == 2
        assert [m["name"] for m in matches] == ["db-inst-1", "db-inst-2"]
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[1][1]["params"] == {"pageToken": "token-page-2"}


def test_fetch_cloud_sql_instances_by_prefix_http_error():
    """Verify _fetch_cloud_sql_instances_by_prefix returns error on HTTP non-200."""
    mock_err = MagicMock(status_code=403)
    with patch("requests.get", return_value=mock_err):
        matches, err = gcp_resources._fetch_cloud_sql_instances_by_prefix("proj", "db-inst", "token")
        assert matches is None
        assert err == "HTTP 403"


def test_get_instance_status_via_compute_v1():
    """Verify get_instance_status retrieves status via compute_v1."""
    mock_client = MagicMock()
    mock_inst = MagicMock()
    mock_inst.status = "RUNNING"
    mock_client.get.return_value = mock_inst
    mock_compute = MagicMock()
    mock_compute.InstancesClient.return_value = mock_client

    status, err = gcp_resources.get_instance_status(
        "sumifu", "asia-northeast1-b", "proxysql-instance-prod", compute_module=mock_compute
    )
    assert status == "RUNNING"
    assert err == ""
    mock_client.get.assert_called_once_with(
        project="sumifu", zone="asia-northeast1-b", instance="proxysql-instance-prod", timeout=10.0
    )


def test_get_instance_status_via_rest_fallback():
    """Verify get_instance_status retrieves status via REST API when compute_v1 unavailable."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "TERMINATED"}

    with patch("requests.get", return_value=mock_resp):
        status, err = gcp_resources.get_instance_status(
            "sumifu",
            "asia-northeast1-b",
            "proxysql-instance-prod",
            compute_module=None,
            get_token_callback=lambda: "mock-token",
        )
        assert status == "TERMINATED"
        assert err == ""


def test_start_proxysql_instance_already_running(monkeypatch):
    """Verify start_proxysql_instance is a no-op if already RUNNING."""
    monkeypatch.setenv("IS_CLOUD", "true")
    with patch.object(gcp_resources, "get_instance_status", return_value=("RUNNING", "")):
        mock_compute = MagicMock()
        res = gcp_resources.start_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=mock_compute,
        )
        assert res is True
        mock_compute.InstancesClient.return_value.start.assert_not_called()


def test_start_proxysql_instance_via_compute_v1(monkeypatch):
    """Verify start_proxysql_instance starts instance via compute_v1."""
    monkeypatch.setenv("IS_CLOUD", "true")
    mock_client = MagicMock()
    mock_compute = MagicMock()
    mock_compute.InstancesClient.return_value = mock_client

    with patch.object(gcp_resources, "get_instance_status", return_value=("TERMINATED", "")):
        res = gcp_resources.start_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=mock_compute,
        )
        assert res is True
        mock_client.start.assert_called_once_with(
            project="sumifu", zone="asia-northeast1-b", instance="proxysql-instance-prod"
        )


def test_start_proxysql_instance_via_rest_fallback(monkeypatch):
    """Verify start_proxysql_instance uses REST fallback if compute_v1 fails."""
    monkeypatch.setenv("IS_CLOUD", "true")
    mock_resp = MagicMock(status_code=200)

    with (
        patch.object(gcp_resources, "get_instance_status", return_value=("TERMINATED", "")),
        patch("requests.post", return_value=mock_resp) as mock_post,
    ):
        res = gcp_resources.start_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=None,
            get_token_callback=lambda: "mock-token",
        )
        assert res is True
        mock_post.assert_called_once()
        assert "proxysql-instance-prod/start" in mock_post.call_args[0][0]


def test_stop_proxysql_instance_already_stopped(monkeypatch):
    """Verify stop_proxysql_instance is a no-op if already TERMINATED."""
    monkeypatch.setenv("IS_CLOUD", "true")
    with patch.object(gcp_resources, "get_instance_status", return_value=("TERMINATED", "")):
        mock_compute = MagicMock()
        res = gcp_resources.stop_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=mock_compute,
        )
        assert res is True
        mock_compute.InstancesClient.return_value.stop.assert_not_called()


def test_stop_proxysql_instance_via_compute_v1(monkeypatch):
    """Verify stop_proxysql_instance stops instance via compute_v1."""
    monkeypatch.setenv("IS_CLOUD", "true")
    mock_client = MagicMock()
    mock_compute = MagicMock()
    mock_compute.InstancesClient.return_value = mock_client

    with patch.object(gcp_resources, "get_instance_status", return_value=("RUNNING", "")):
        res = gcp_resources.stop_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=mock_compute,
        )
        assert res is True
        mock_client.stop.assert_called_once_with(
            project="sumifu", zone="asia-northeast1-b", instance="proxysql-instance-prod"
        )


def test_stop_proxysql_instance_via_rest_fallback(monkeypatch):
    """Verify stop_proxysql_instance uses REST fallback if compute_v1 fails."""
    monkeypatch.setenv("IS_CLOUD", "true")
    mock_resp = MagicMock(status_code=200)

    with (
        patch.object(gcp_resources, "get_instance_status", return_value=("RUNNING", "")),
        patch("requests.post", return_value=mock_resp) as mock_post,
    ):
        res = gcp_resources.stop_proxysql_instance(
            project_id="sumifu",
            zone="asia-northeast1-b",
            instance_name="proxysql-instance-prod",
            compute_module=None,
            get_token_callback=lambda: "mock-token",
        )
        assert res is True
        mock_post.assert_called_once()
        assert "proxysql-instance-prod/stop" in mock_post.call_args[0][0]


def test_scale_proxysql_mig_delegates_to_single_instance(monkeypatch):
    """Verify scale_proxysql_mig delegates to start/stop instance when PROXYSQL_INSTANCE_NAME is set."""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")
    monkeypatch.setenv("PROXYSQL_ZONE", "asia-northeast1-b")

    with patch.object(gcp_resources, "start_proxysql_instance", return_value=True) as mock_start:
        assert gcp_resources.scale_proxysql_mig(target_size=1) is True
        mock_start.assert_called_once()

    with patch.object(gcp_resources, "stop_proxysql_instance", return_value=True) as mock_stop:
        assert gcp_resources.scale_proxysql_mig(target_size=0) is True
        mock_stop.assert_called_once()






