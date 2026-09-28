# -*- coding: utf-8 -*-
"""Pipeline Coordinator バリア同期の単体テスト."""
import logging
from unittest.mock import MagicMock

from package.utils.pipeline_coordinator import check_all_tasks_completed, wait_for_all_tasks


def _recs(status_by_index):
    return [MagicMock(task_index=i, status=s) for i, s in status_by_index.items()]


def test_check_all_tasks_completed_single_task_is_always_complete():
    assert check_all_tasks_completed([], task_count=1) == (True, [])


def test_wait_single_task_returns_without_query():
    model = MagicMock()
    assert wait_for_all_tasks(model, "d", task_count=1) == (True, [])
    model.objects.filter.assert_not_called()


def test_wait_returns_failed_indices_when_all_terminal():
    model = MagicMock()
    model.objects.filter.return_value = _recs({0: "COMPLETED", 1: "FAILED"})
    assert wait_for_all_tasks(model, "d", task_count=2, timeout_sec=30, interval_sec=0) == (True, [1])
    model.objects.filter.assert_called_once_with(execution_date="d")


def test_wait_polls_until_complete_and_logs_progress(caplog):
    model = MagicMock()
    model.objects.filter.side_effect = [
        _recs({0: "COMPLETED", 1: "RUNNING", 2: "RUNNING"}),
        _recs({0: "COMPLETED", 1: "COMPLETED", 2: "FAILED"}),
    ]
    with caplog.at_level(logging.INFO, logger="package.utils.pipeline_coordinator"):
        result = wait_for_all_tasks(model, "d", task_count=3, timeout_sec=30, interval_sec=0, execution_id="e1")
    assert result == (True, [2])
    assert "進行状況: 1/3 タスク完了" in caplog.text
    assert model.objects.filter.call_count == 2
    model.objects.filter.assert_called_with(execution_date="d", execution_id="e1")


def test_wait_timeout_returns_false_with_failed_indices():
    model = MagicMock()
    model.objects.filter.return_value = _recs({0: "COMPLETED", 1: "FAILED"})
    assert wait_for_all_tasks(model, "d", task_count=2, timeout_sec=0, interval_sec=0) == (False, [1])


def test_check_all_tasks_completed_success():
    # 4タスクすべて COMPLETED
    records = [
        MagicMock(task_index=0, status="COMPLETED"),
        MagicMock(task_index=1, status="COMPLETED"),
        MagicMock(task_index=2, status="COMPLETED"),
        MagicMock(task_index=3, status="COMPLETED"),
    ]
    completed, failed = check_all_tasks_completed(records, task_count=4)
    assert completed is True
    assert failed == []


def test_check_all_tasks_completed_pending():
    # Task 2 が未完了 (RUNNING)
    records = [
        MagicMock(task_index=0, status="COMPLETED"),
        MagicMock(task_index=1, status="COMPLETED"),
        MagicMock(task_index=2, status="RUNNING"),
        MagicMock(task_index=3, status="COMPLETED"),
    ]
    completed, failed = check_all_tasks_completed(records, task_count=4)
    assert completed is False


def test_check_all_tasks_completed_missing_task():
    # Task 3 のレコードがまだ作成されていない
    records = [
        MagicMock(task_index=0, status="COMPLETED"),
        MagicMock(task_index=1, status="COMPLETED"),
        MagicMock(task_index=2, status="COMPLETED"),
    ]
    completed, failed = check_all_tasks_completed(records, task_count=4)
    assert completed is False


def test_check_all_tasks_completed_with_failed_task():
    # Task 1 が FAILED
    records = [
        MagicMock(task_index=0, status="COMPLETED"),
        MagicMock(task_index=1, status="FAILED"),
        MagicMock(task_index=2, status="COMPLETED"),
        MagicMock(task_index=3, status="COMPLETED"),
    ]
    completed, failed = check_all_tasks_completed(records, task_count=4)
    # FAILED も終了状態とみなすが failed リストに含まれる
    assert completed is True
    assert failed == [1]
