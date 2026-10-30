from unittest.mock import patch

import pytest

from scripts.ensure_resources_stopped import (
    DEFAULT_MAX_UPTIME_SEC,
    check_and_stop_proxysql_instance,
)


@pytest.fixture
def mock_deps():
    with patch("scripts.ensure_resources_stopped._get_instance_info") as m_info, \
         patch("scripts.ensure_resources_stopped._get_active_cloud_run_executions") as m_active, \
         patch("scripts.ensure_resources_stopped._get_instance_network_received_bytes") as m_traffic, \
         patch("scripts.ensure_resources_stopped._stop_instance") as m_stop, \
         patch("scripts.ensure_resources_stopped.send_slack_alert") as m_slack, \
         patch("scripts.ensure_resources_stopped.send_slack_info") as m_info_slack:
        yield {
            "info": m_info,
            "active": m_active,
            "traffic": m_traffic,
            "stop": m_stop,
            "slack": m_slack,
            "info_slack": m_info_slack,
        }


def test_active_traffic_skips_stop(mock_deps):
    """Cloud Run Job が 0件でも、直近10分間の受信トラフィックが1MB以上あれば停止をスキップする"""
    mock_deps["info"].return_value = ("RUNNING", "", 1800.0)  # 30分稼働
    mock_deps["active"].return_value = ([], "")  # Cloud Run Job 0件
    mock_deps["traffic"].return_value = (2 * 1024 * 1024, "")  # 2 MB 受信

    result = check_and_stop_proxysql_instance(
        project_id="sumifu",
        zone="asia-northeast1-a",
        instance_name="proxysql-instance-prod",
    )

    assert result.was_leaked is False
    assert result.forced_stop is False
    assert result.skipped_reason == "active_traffic"
    mock_deps["stop"].assert_not_called()
    mock_deps["info_slack"].assert_called_once()
    mock_deps["slack"].assert_not_called()


def test_low_traffic_triggers_stop(mock_deps):
    """Cloud Run Job が 0件で、受信トラフィックがヘルスチェック程度（1MB未満）の場合は停止する"""
    mock_deps["info"].return_value = ("RUNNING", "", 1800.0)
    mock_deps["active"].return_value = ([], "")
    mock_deps["traffic"].return_value = (50 * 1024, "")  # 50 KB 受信 (ヘルスチェックのみ)
    mock_deps["stop"].return_value = ""  # 正常停止

    result = check_and_stop_proxysql_instance(
        project_id="sumifu",
        zone="asia-northeast1-a",
        instance_name="proxysql-instance-prod",
    )

    assert result.was_leaked is True
    assert result.forced_stop is True
    mock_deps["stop"].assert_called_once_with("sumifu", "asia-northeast1-a", "proxysql-instance-prod")


def test_max_uptime_exceeded_forces_stop(mock_deps):
    """稼働時間が8時間を超過した場合は、トラフィックがあってもハング防止のため強制停止する"""
    mock_deps["info"].return_value = ("RUNNING", "", DEFAULT_MAX_UPTIME_SEC + 100.0)  # 8時間超
    mock_deps["active"].return_value = ([], "")
    mock_deps["stop"].return_value = ""

    result = check_and_stop_proxysql_instance(
        project_id="sumifu",
        zone="asia-northeast1-a",
        instance_name="proxysql-instance-prod",
    )

    assert result.was_leaked is True
    assert result.forced_stop is True
    assert result.skipped_reason == "max_uptime_exceeded"
    mock_deps["stop"].assert_called_once_with("sumifu", "asia-northeast1-a", "proxysql-instance-prod")
    mock_deps["traffic"].assert_not_called()  # 上限超過時は即時停止


def test_traffic_api_error_defers_stop(mock_deps):
    """Cloud Monitoring API がエラーを返した場合は、稼働中インスタンス誤停止防止のため停止を保留する"""
    mock_deps["info"].return_value = ("RUNNING", "", 1800.0)
    mock_deps["active"].return_value = ([], "")
    mock_deps["traffic"].return_value = (None, "Monitoring API unavailable")
    mock_deps["stop"].return_value = ""

    result = check_and_stop_proxysql_instance(
        project_id="sumifu",
        zone="asia-northeast1-a",
        instance_name="proxysql-instance-prod",
    )

    assert result.was_leaked is False
    assert result.forced_stop is False
    assert result.skipped_reason == "traffic_unknown"
    mock_deps["stop"].assert_not_called()
