# -*- coding: utf-8 -*-
"""Issue #916: run_pipeline._can_stop_shared_proxysql が単独タスク・タスクアレイ問わず他Cloud Run実行稼働時に停止拒否することを検証"""
from unittest.mock import MagicMock, patch
import pytest

from scripts.ops import run_pipeline


@pytest.fixture(autouse=True)
def reset_pipeline_globals():
    run_pipeline._task_count = 1
    run_pipeline._task_index = 0
    run_pipeline._is_coordinator = True
    run_pipeline._teardown_done = False
    yield


def test_single_task_blocked_when_other_cloud_run_executions_active(monkeypatch):
    """単独タスク実行 (_task_count <= 1) であっても他Cloud Run実行が稼働中の場合は停止をスキップすること"""
    run_pipeline._task_count = 1
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "crawler-single-job-xyz")

    with patch.object(run_pipeline, "has_active_other_cloud_run_executions", return_value=True) as mock_check:
        can_stop = run_pipeline._can_stop_shared_proxysql()
        assert can_stop is False
        mock_check.assert_called_once()


def test_single_task_allowed_when_no_other_cloud_run_executions_active(monkeypatch):
    """単独タスク実行 (_task_count <= 1) で他Cloud Run実行が稼働していない場合は停止を許可すること"""
    run_pipeline._task_count = 1
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "crawler-single-job-xyz")

    with patch.object(run_pipeline, "has_active_other_cloud_run_executions", return_value=False) as mock_check:
        can_stop = run_pipeline._can_stop_shared_proxysql()
        assert can_stop is True
        mock_check.assert_called_once()


def test_task_array_blocked_when_other_cloud_run_executions_active(monkeypatch):
    """タスクアレイで全自タスクがCOMPLETEDでも他Cloud Run実行が稼働中の場合は停止をスキップすること"""
    run_pipeline._task_count = 2
    run_pipeline._task_index = 0
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "crawler-array-job-abc")

    mock_rec0 = MagicMock(task_index=0, status="COMPLETED")
    mock_rec1 = MagicMock(task_index=1, status="COMPLETED")

    with patch("scripts.ops.run_pipeline.CrawlerTaskExecution.objects.filter", return_value=[mock_rec0, mock_rec1]), \
         patch.object(run_pipeline, "_bind_parent_db_timeouts"), \
         patch.object(run_pipeline, "has_active_other_cloud_run_executions", return_value=True) as mock_check:
        can_stop = run_pipeline._can_stop_shared_proxysql()
        assert can_stop is False
        mock_check.assert_called_once()


def test_task_array_allowed_when_all_tasks_done_and_no_other_executions(monkeypatch):
    """タスクアレイで全タスク完了かつ他Cloud Run実行が無い場合は停止を許可すること"""
    run_pipeline._task_count = 2
    run_pipeline._task_index = 0
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "crawler-array-job-abc")

    mock_rec0 = MagicMock(task_index=0, status="COMPLETED")
    mock_rec1 = MagicMock(task_index=1, status="COMPLETED")

    with patch("scripts.ops.run_pipeline.CrawlerTaskExecution.objects.filter", return_value=[mock_rec0, mock_rec1]), \
         patch.object(run_pipeline, "_bind_parent_db_timeouts"), \
         patch.object(run_pipeline, "has_active_other_cloud_run_executions", return_value=False) as mock_check:
        can_stop = run_pipeline._can_stop_shared_proxysql()
        assert can_stop is True
        mock_check.assert_called_once()
