"""Crawler process watchdog module for detecting silent hanging jobs."""
import logging
import os
import signal
import time
from typing import Any

logger = logging.getLogger(__name__)

def _parse_hang_threshold() -> float:
    raw = os.getenv("CRAWLER_HANG_THRESHOLD_SEC", "0.0").strip()
    try:
        val = float(raw)
        return max(0.0, val)
    except (ValueError, TypeError):
        return 0.0

HANG_THRESHOLD_SEC: float = _parse_hang_threshold()


def check_job_hung(
    last_activity_time: float,
    current_time: float | None = None,
    threshold_sec: float = HANG_THRESHOLD_SEC,
) -> bool:
    """Check if job has been silent (no heartbeat/progress) for longer than threshold."""
    if threshold_sec <= 0:
        return False
    now = current_time if current_time is not None else time.time()
    return (now - last_activity_time) > threshold_sec


def kill_hung_job_process(proc: Any) -> bool:
    """Terminate hung job process group via SIGKILL."""
    if proc is None or proc.poll() is not None:
        return False
    try:
        pgid = os.getpgid(proc.pid)
        logger.warning(
            f"⚠️ [Watchdog Hang Detected] Process group {pgid} (PID {proc.pid}) "
            f"silent > {HANG_THRESHOLD_SEC}s. Killing process group via SIGKILL..."
        )
        os.killpg(pgid, signal.SIGKILL)
        proc.communicate()
        return True
    except Exception:
        logger.exception("Failed to kill hung process group")
        return False


def _update_single_job_progress(
    job_info: tuple,
    now: float,
    count_fn: Any,
    check_interval_sec: float,
) -> tuple:
    """単一ジョブのDB進捗を確認し、更新後のタプルを返す"""
    proc, company, ptype, start_t, start_dt, *extra = job_info
    last_act = extra[0] if extra else start_t
    prev_db_cnt = extra[1] if len(extra) > 1 else 0
    last_check_t = extra[2] if len(extra) > 2 else 0.0

    if (now - last_check_t) < check_interval_sec:
        return job_info

    counts = count_fn(company, ptype, start_dt)
    current_db_cnt = counts[2] if counts[0] is not None else None
    if current_db_cnt is not None:
        if current_db_cnt > prev_db_cnt:
            last_act = now
        return (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
    return (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)


def update_watchdog_progress(
    active_processes: dict[int, tuple],
    now: float,
    count_fn: Any,
    check_interval_sec: float = 15.0,
) -> None:
    """進捗監視対象プロセスのDB件数増分を確認し、公平に last_act を更新する"""
    for idx in tuple(active_processes.keys()):
        if idx in active_processes:
            active_processes[idx] = _update_single_job_progress(
                active_processes[idx], now, count_fn, check_interval_sec
            )
