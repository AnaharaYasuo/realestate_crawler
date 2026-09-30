"""Crawler process watchdog module for detecting silent hanging jobs."""
import logging
import os
import signal
import time
from typing import Any

logger = logging.getLogger(__name__)

# ジョブの無進捗・沈黙判定閾値（秒）: ハートビート連携未完時は誤殺害防止のため 0.0 (無効) をデフォルトとし、CRAWLER_HANG_THRESHOLD_SEC 指定時のみ有効化
HANG_THRESHOLD_SEC: float = float(os.getenv("CRAWLER_HANG_THRESHOLD_SEC", "0.0"))


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
