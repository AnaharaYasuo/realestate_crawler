# -*- coding: utf-8 -*-
"""Issue #518: クローリング中の ProxySQL/DB 死活監視連動 Fast-Fail の単体テスト"""
import argparse
import signal
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.ops import run_all_crawlers as rac

_MOD = "scripts.ops.run_all_crawlers"


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, sec: float) -> None:
        self.now += sec


class FakeConnector:
    """socket.create_connection 互換。outcomes の True=成功 / False=OSError を順に返す"""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, address, timeout=None):
        self.calls.append((address, timeout))
        if not self.outcomes.pop(0):
            raise ConnectionRefusedError("Connection refused")
        return MagicMock()


def _monitor(outcomes, clock=None, interval=15.0, max_failures=3):
    connector = FakeConnector(outcomes)
    monitor = rac.DbLivenessMonitor(
        "10.0.0.10",
        6033,
        interval_sec=interval,
        max_failures=max_failures,
        timeout_sec=3.0,
        connector=connector,
        clock=clock or FakeClock(),
    )
    return monitor, connector


@pytest.fixture(autouse=True)
def _reset_active_processes():
    rac.active_processes.clear()
    yield
    rac.active_processes.clear()


# --- 設定値 ---

def test_default_thresholds():
    assert rac.DB_HEALTH_CHECK_INTERVAL_SEC == 15.0
    assert rac.DB_HEALTH_MAX_CONSECUTIVE_FAILURES == 3
    assert rac.DB_HEALTH_SOCKET_TIMEOUT_SEC == 3.0


# --- DbLivenessMonitor ---

def test_monitor_connects_to_target_with_finite_timeout():
    monitor, connector = _monitor([True])
    assert monitor.is_lost() is False
    assert connector.calls == [(("10.0.0.10", 6033), 3.0)]
    assert monitor.consecutive_failures == 0


def test_monitor_trips_only_after_consecutive_failures_reach_threshold():
    clock = FakeClock()
    monitor, _ = _monitor([False, False, False], clock=clock)

    assert monitor.is_lost() is False
    assert monitor.consecutive_failures == 1
    clock.advance(15.0)
    assert monitor.is_lost() is False
    assert monitor.consecutive_failures == 2
    clock.advance(15.0)
    assert monitor.is_lost() is True
    assert monitor.consecutive_failures == 3
    assert "Connection refused" in monitor.last_error


def test_monitor_success_resets_failure_counter():
    clock = FakeClock()
    monitor, _ = _monitor([False, False, True, False, False], clock=clock)

    results = []
    for _ in range(5):
        results.append(monitor.is_lost())
        clock.advance(15.0)

    assert results == [False, False, False, False, False]
    assert monitor.consecutive_failures == 2


def test_monitor_skips_probe_until_interval_elapsed():
    clock = FakeClock()
    monitor, connector = _monitor([False, False], clock=clock)

    monitor.is_lost()
    clock.advance(14.9)
    assert monitor.is_lost() is False
    assert len(connector.calls) == 1

    clock.advance(0.1)
    monitor.is_lost()
    assert len(connector.calls) == 2


def test_monitor_keeps_lost_state_between_probes():
    clock = FakeClock()
    monitor, connector = _monitor([False], clock=clock, max_failures=1)

    assert monitor.is_lost() is True
    clock.advance(1.0)
    assert monitor.is_lost() is True
    assert len(connector.calls) == 1


def test_monitor_treats_timeout_as_failure():
    def connector(address, timeout=None):
        raise TimeoutError("timed out")

    monitor = rac.DbLivenessMonitor("10.0.0.10", 6033, max_failures=1, connector=connector, clock=FakeClock())
    assert monitor.is_lost() is True
    assert "timed out" in monitor.last_error


def test_monitor_coerces_string_port():
    monitor = rac.DbLivenessMonitor("db", "3306", connector=FakeConnector([True]), clock=FakeClock())
    assert monitor.port == 3306


# --- resolve_db_endpoint ---

def test_resolve_db_endpoint_prefers_django_settings(monkeypatch):
    monkeypatch.setenv("DB_HOST", "env-host")
    monkeypatch.setenv("DB_PORT", "1111")
    fake_conn = MagicMock(settings_dict={"HOST": "10.0.0.10", "PORT": "6033"})
    with patch(f"{_MOD}.connection", fake_conn):
        assert rac.resolve_db_endpoint() == ("10.0.0.10", 6033)


def test_resolve_db_endpoint_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("DB_HOST", "env-host")
    monkeypatch.setenv("DB_PORT", "6033")
    fake_conn = MagicMock(settings_dict={"HOST": "", "PORT": ""})
    with patch(f"{_MOD}.connection", fake_conn):
        assert rac.resolve_db_endpoint() == ("env-host", 6033)


# --- abort_on_db_liveness_loss ---

def _lost_monitor():
    monitor, _ = _monitor([False], max_failures=1)
    monitor.is_lost()
    return monitor


def test_abort_kills_children_alerts_marks_failed_and_exits_nonzero():
    calls = []
    record = MagicMock()
    record.save.side_effect = lambda: calls.append("save")
    rac.active_processes[1] = (MagicMock(), "keio", "mansion", 0.0, None)
    rac.active_processes[2] = (MagicMock(), "odakyu", "kodate", 0.0, None)

    alert = AsyncMock(side_effect=lambda msg: calls.append(("alert", msg)))
    with (
        patch(f"{_MOD}.cleanup_active_process", side_effect=lambda: calls.append("cleanup")) as mock_cleanup,
        patch(f"{_MOD}.send_crawling_summary_alert", alert),
    ):
        with pytest.raises(SystemExit) as exc:
            rac.abort_on_db_liveness_loss(_lost_monitor(), record)

    assert exc.value.code == 1
    mock_cleanup.assert_called_once()
    assert [c if isinstance(c, str) else c[0] for c in calls] == ["cleanup", "alert", "save"]
    msg = calls[1][1]
    assert "10.0.0.10:6033" in msg
    assert "keio - mansion" in msg and "odakyu - kodate" in msg
    assert "連続 1 回" in msg
    assert record.status == "FAILED"


def test_abort_still_exits_when_alert_and_db_update_fail():
    record = MagicMock()
    record.save.side_effect = RuntimeError("db down")
    with (
        patch(f"{_MOD}.cleanup_active_process") as mock_cleanup,
        patch(f"{_MOD}.send_crawling_summary_alert", AsyncMock(side_effect=RuntimeError("slack down"))),
    ):
        with pytest.raises(SystemExit) as exc:
            rac.abort_on_db_liveness_loss(_lost_monitor(), record)

    assert exc.value.code == 1
    mock_cleanup.assert_called_once()


def test_abort_does_not_hang_when_db_save_blocks():
    """DB 不通で save() がブロックしても、有限時間で見切って exit 1 する"""
    release = threading.Event()
    record = MagicMock()
    record.save.side_effect = lambda: release.wait(5)
    try:
        with (
            patch(f"{_MOD}.cleanup_active_process"),
            patch(f"{_MOD}.send_crawling_summary_alert", AsyncMock()),
            patch(f"{_MOD}.DB_LIVENESS_ABORT_SAVE_TIMEOUT_SEC", 0.2),
        ):
            started = time.monotonic()
            with pytest.raises(SystemExit) as exc:
                rac.abort_on_db_liveness_loss(_lost_monitor(), record)
            elapsed = time.monotonic() - started
    finally:
        release.set()

    assert exc.value.code == 1
    assert elapsed < 2.0
    record.save.assert_called_once()


def test_abort_save_timeout_default():
    assert rac.DB_LIVENESS_ABORT_SAVE_TIMEOUT_SEC == 10.0


def test_abort_without_task_record_and_no_active_jobs():
    alert = AsyncMock()
    with (
        patch(f"{_MOD}.cleanup_active_process"),
        patch(f"{_MOD}.send_crawling_summary_alert", alert),
    ):
        with pytest.raises(SystemExit) as exc:
            rac.abort_on_db_liveness_loss(_lost_monitor(), None)

    assert exc.value.code == 1
    assert "停止ジョブ: なし" in alert.call_args[0][0]


# --- main() ループ統合 ---

def test_main_loop_fast_fails_running_crawlers_when_db_is_lost():
    """ジョブ起動後に DB 応答喪失を検知したら、子プロセスグループを SIGKILL し exit 1 で終了する"""
    args = argparse.Namespace(dry_run=False, parallel=1, playwright_parallel=1, skip_portals=False)
    fake_proc = MagicMock(pid=1234)
    fake_proc.poll.return_value = None
    fake_monitor = MagicMock(host="10.0.0.10", port=6033, consecutive_failures=3, last_error="refused")
    fake_monitor.is_lost.side_effect = [False, True]
    record = MagicMock()
    task_exec = MagicMock()
    task_exec.objects.update_or_create.return_value = (record, True)
    alert = AsyncMock()

    with (
        patch(f"{_MOD}.parse_args", return_value=args),
        patch(f"{_MOD}.clean_zombies"),
        patch(f"{_MOD}.get_task_config", return_value=(None, 1)),
        patch(f"{_MOD}.CRAWL_JOBS", [("keio", "mansion"), ("odakyu", "kodate")]),
        patch(f"{_MOD}.select_next_job", return_value=(0, None)),
        patch(f"{_MOD}.CrawlerTaskExecution", task_exec),
        patch(f"{_MOD}.send_crawling_summary_alert", alert),
        patch(f"{_MOD}.resolve_db_endpoint", return_value=("10.0.0.10", 6033)),
        patch(f"{_MOD}.DbLivenessMonitor", return_value=fake_monitor) as monitor_cls,
        patch(f"{_MOD}.subprocess.Popen", return_value=fake_proc) as mock_popen,
        patch(f"{_MOD}.os.getpgid", return_value=4321, create=True),
        patch(f"{_MOD}.os.killpg", create=True) as mock_killpg,
        patch(f"{_MOD}.time.sleep"),
    ):
        with pytest.raises(SystemExit) as exc:
            rac.main()

    assert exc.value.code == 1
    monitor_cls.assert_called_once_with("10.0.0.10", 6033)
    mock_popen.assert_called_once()
    mock_killpg.assert_called_once_with(4321, signal.SIGKILL)
    assert rac.active_processes == {}
    assert record.status == "FAILED"
    alert_msgs = [c.args[0] for c in alert.call_args_list]
    assert any("keio - mansion" in m and "10.0.0.10:6033" in m for m in alert_msgs)
