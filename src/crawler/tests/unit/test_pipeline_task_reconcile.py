# -*- coding: utf-8 -*-
"""Issue #518: DB 応答喪失で RUNNING のまま残った CrawlerTaskExecution を DB 復旧後に FAILED へ再同期するテスト"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.db import OperationalError

from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.pipeline_coordinator import wait_for_all_tasks
from scripts.ops import run_pipeline

_MOD = "scripts.ops.run_pipeline"


def _today():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().date()


@pytest.fixture(autouse=True)
def _clean_task_executions():
    CrawlerTaskExecution.objects.all().delete()
    yield
    CrawlerTaskExecution.objects.all().delete()


@pytest.fixture(autouse=True)
def fake_connection():
    conn = MagicMock(settings_dict={"ENGINE": "django.db.backends.mysql", "OPTIONS": {"charset": "utf8mb4"}})
    with patch(f"{_MOD}.connection", conn):
        yield conn


def _create(task_index, status, task_count=2):
    return CrawlerTaskExecution.objects.create(
        execution_date=_today(), task_index=task_index, task_count=task_count, status=status
    )


def test_reconcile_marks_only_own_running_task_failed():
    """自タスクの RUNNING 行のみ FAILED に更新し、他タスクや終端状態の行は変更しないこと"""
    own = _create(1, "RUNNING")
    other_running = _create(2, "RUNNING")
    other_completed = _create(0, "COMPLETED")

    with patch(f"{_MOD}.time.sleep") as mock_sleep:
        assert run_pipeline.reconcile_aborted_task_execution(1) is True

    mock_sleep.assert_not_called()
    own.refresh_from_db()
    other_running.refresh_from_db()
    other_completed.refresh_from_db()
    assert own.status == "FAILED"
    assert other_running.status == "RUNNING"
    assert other_completed.status == "COMPLETED"


def test_reconcile_does_not_overwrite_completed_own_task():
    """自タスクが既に COMPLETED の場合は FAILED に上書きしないこと"""
    own = _create(0, "COMPLETED", task_count=1)

    assert run_pipeline.reconcile_aborted_task_execution(None) is True

    own.refresh_from_db()
    assert own.status == "COMPLETED"


def test_reconcile_retries_until_db_recovers():
    """DB 不通中は切断済み接続を破棄して一定間隔で再試行し、復旧後に更新できたら成功を返すこと"""
    qs = MagicMock()
    qs.update.side_effect = [OperationalError("gone"), OperationalError("gone"), 1]
    with patch(f"{_MOD}.CrawlerTaskExecution.objects.filter", return_value=qs) as mock_filter, \
         patch(f"{_MOD}.close_old_connections") as mock_close, \
         patch(f"{_MOD}.time.sleep") as mock_sleep:
        assert run_pipeline.reconcile_aborted_task_execution(3) is True

    mock_filter.assert_called_with(execution_date=_today(), task_index=3, status="RUNNING")
    qs.update.assert_called_with(status="FAILED")
    assert qs.update.call_count == 3
    assert mock_close.call_count == 3
    assert [c.args[0] for c in mock_sleep.call_args_list] == [run_pipeline.TASK_RECONCILE_INTERVAL_SEC] * 2


def test_reconcile_gives_up_after_bounded_attempts():
    """DB が復旧しない場合は有限回で諦め、例外を送出せず False を返すこと"""
    qs = MagicMock()
    qs.update.side_effect = OperationalError("gone")
    with patch(f"{_MOD}.CrawlerTaskExecution.objects.filter", return_value=qs), \
         patch(f"{_MOD}.close_old_connections"), \
         patch(f"{_MOD}.time.sleep") as mock_sleep:
        assert run_pipeline.reconcile_aborted_task_execution(1) is False

    assert qs.update.call_count == run_pipeline.TASK_RECONCILE_MAX_ATTEMPTS == 4
    assert mock_sleep.call_count == run_pipeline.TASK_RECONCILE_MAX_ATTEMPTS - 1


def test_reconcile_bounds_parent_db_timeouts_before_first_attempt(fake_connection):
    """親プロセスの MySQL 接続にも有限の接続・読み書きタイムアウトを適用してから DB 更新を試行すること"""
    options_at_update = []
    qs = MagicMock()
    qs.update.side_effect = lambda **kw: options_at_update.append(dict(fake_connection.settings_dict["OPTIONS"])) or 1
    with patch(f"{_MOD}.CrawlerTaskExecution.objects.filter", return_value=qs), \
         patch(f"{_MOD}.close_old_connections"):
        assert run_pipeline.reconcile_aborted_task_execution(0) is True

    assert options_at_update == [{
        "charset": "utf8mb4",
        "connect_timeout": 10,
        "read_timeout": 120,
        "write_timeout": 120,
    }]


def test_reconcile_skips_attempt_when_deadline_approaching():
    """デッドライン接近時は DB 更新を試行せず False を返すこと"""
    with patch(f"{_MOD}.is_deadline_approaching", return_value=True), \
         patch(f"{_MOD}.CrawlerTaskExecution.objects.filter") as mock_filter, \
         patch(f"{_MOD}.close_old_connections"), \
         patch(f"{_MOD}.time.sleep") as mock_sleep:
        assert run_pipeline.reconcile_aborted_task_execution(1) is False

    mock_filter.assert_not_called()
    mock_sleep.assert_not_called()


def test_reconcile_stops_retrying_when_deadline_approaches_before_sleep():
    """失敗後のリトライ待機前にデッドライン接近を検知したら待機せず打ち切ること"""
    qs = MagicMock()
    qs.update.side_effect = OperationalError("gone")
    with patch(f"{_MOD}.is_deadline_approaching", side_effect=[False, True]), \
         patch(f"{_MOD}.CrawlerTaskExecution.objects.filter", return_value=qs), \
         patch(f"{_MOD}.close_old_connections"), \
         patch(f"{_MOD}.time.sleep") as mock_sleep:
        assert run_pipeline.reconcile_aborted_task_execution(1) is False

    assert qs.update.call_count == 1
    mock_sleep.assert_not_called()


def test_reconcile_pre_sleep_deadline_check_accounts_for_wait_interval():
    """リトライ待機前のデッドライン判定は、これから待機する時間も含めた猶予で行うこと"""
    qs = MagicMock()
    qs.update.side_effect = [OperationalError("gone"), 1]
    with patch(f"{_MOD}.is_deadline_approaching", return_value=False) as mock_deadline, \
         patch(f"{_MOD}.CrawlerTaskExecution.objects.filter", return_value=qs), \
         patch(f"{_MOD}.close_old_connections"), \
         patch(f"{_MOD}.time.sleep"):
        assert run_pipeline.reconcile_aborted_task_execution(1) is True

    buffers = [c.args[0] if c.args else None for c in mock_deadline.call_args_list]
    assert buffers == [
        None,
        run_pipeline.SAFE_SHUTDOWN_BUFFER_SEC + run_pipeline.TASK_RECONCILE_INTERVAL_SEC,
        None,
    ]


def test_reconciled_task_lets_barrier_exit_without_waiting():
    """再同期後はバリアが対象タスクを終端状態とみなし、待機せずに即時終了すること"""
    _create(0, "COMPLETED")
    _create(1, "RUNNING")

    with patch(f"{_MOD}.time.sleep"):
        run_pipeline.reconcile_aborted_task_execution(1)
    with patch("package.utils.pipeline_coordinator.time.sleep") as barrier_sleep:
        all_ok, failed = wait_for_all_tasks(
            CrawlerTaskExecution, _today(), task_count=2, timeout_sec=1800, interval_sec=15
        )

    assert (all_ok, failed) == (True, [1])
    barrier_sleep.assert_not_called()


def _run_step(is_task_array, is_coordinator, task_index):
    return run_pipeline._run_crawler_step(
        is_task_array=is_task_array,
        is_coordinator=is_coordinator,
        task_index=task_index,
        task_count=2 if is_task_array else 1,
        ops_dir="/tmp/ops",
        skip_portals=False,
    )


def test_worker_crawl_failure_reconciles_own_task():
    """Worker でクローラーが失敗終了した場合、終了前に自タスクを再同期すること"""
    with patch(f"{_MOD}.run_command", side_effect=RuntimeError("exit code 1")), \
         patch(f"{_MOD}.reconcile_aborted_task_execution") as mock_reconcile:
        assert _run_step(True, False, 1) == (False, False)

    mock_reconcile.assert_called_once_with(1)


def test_coordinator_crawl_failure_reconciles_before_barrier():
    """Coordinator でクローラーが失敗終了した場合、バリア待機より前に自タスクを再同期すること"""
    calls = []
    with patch(f"{_MOD}.run_command", side_effect=RuntimeError("exit code 1")), \
         patch(f"{_MOD}.reconcile_aborted_task_execution", side_effect=lambda idx: calls.append(("reconcile", idx))), \
         patch(f"{_MOD}.wait_for_all_tasks", side_effect=lambda **kw: calls.append(("barrier", None)) or (True, [0])), \
         patch(f"{_MOD}.CrawlerTaskExecution.objects.filter") as mock_filter, \
         patch(f"{_MOD}.send_crawling_summary_alert"):
        mock_filter.return_value.order_by.return_value = []
        should_continue, crawler_ok = _run_step(True, True, 0)

    assert should_continue is True and crawler_ok is False
    assert calls[:2] == [("reconcile", 0), ("barrier", None)]


def test_crawl_success_does_not_reconcile():
    """クローラーが正常終了した場合は再同期しないこと"""
    with patch(f"{_MOD}.run_command", return_value=True), \
         patch(f"{_MOD}.reconcile_aborted_task_execution") as mock_reconcile:
        assert _run_step(False, True, None) == (True, True)

    mock_reconcile.assert_not_called()


def test_crawl_timeout_reraises_without_reconcile():
    """TimeoutError は安全停止のため再送出し、再同期は行わないこと"""
    with patch(f"{_MOD}.run_command", side_effect=TimeoutError("deadline")), \
         patch(f"{_MOD}.reconcile_aborted_task_execution") as mock_reconcile:
        with pytest.raises(TimeoutError):
            _run_step(True, False, 1)

    mock_reconcile.assert_not_called()
