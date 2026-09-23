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
    mock_instance.resize.assert_not_called()
    mock_slack.assert_not_called()


def test_proxysql_leaked_triggers_forced_stop_and_alert(mock_compute_client, mock_slack):
    """When target_size > 0, resize(size=0) is called and Slack warning is emitted."""
    mock_instance = MagicMock()
    mock_compute_client.return_value = mock_instance

    mock_igm = MagicMock()
    mock_igm.target_size = 2
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
        region_instance_group_manager="proxysql-mig-prod",
        size=0,
    )
    mock_slack.assert_called_once()
    assert "ProxySQL" in mock_slack.call_args[0][0]


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
