# -*- coding: utf-8 -*-
"""Pipeline Coordinator バリア同期の単体テスト."""
from unittest.mock import MagicMock
from package.utils.pipeline_coordinator import check_all_tasks_completed


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
