# -*- coding: utf-8 -*-
"""Unit tests for gcp_resources utility module (ProxySQL MIG, GCE, Auth)."""

from unittest.mock import MagicMock, patch
import pytest

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

    with patch.object(gcp_resources, "google", None), \
         patch("requests.get", return_value=mock_resp) as mock_get:
        token = gcp_resources.get_gcp_access_token()
        assert token == "metadata-token-456"
        mock_get.assert_called_once()


def test_get_gcp_access_token_returns_none_on_all_failures():
    """Verify get_gcp_access_token returns None if both auth and metadata fail."""
    with patch.object(gcp_resources, "google", None), \
         patch("requests.get", side_effect=Exception("Metadata server error")):
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
        region_instance_group_manager="proxysql-mig-prod",
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

    res = gcp_resources.scale_proxysql_mig(
        target_size=0,
        compute_module=None,
        get_token_callback=lambda: "bearer-token-789",
    )
    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = gcp_resources.scale_proxysql_mig(
            target_size=0,
            compute_module=None,
            get_token_callback=lambda: "bearer-token-789",
        )
        assert res is True
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
