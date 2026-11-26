"""Stop-time (daily cutoff) helper for crawler CLI and daily batch runner (Issue #1845)."""
from __future__ import annotations

import datetime
import logging
import os
import re
import threading
import time
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_DAILY_STOP_TIME = "11:30"
DEFAULT_STOP_TIME_TZ = "Asia/Tokyo"
_DISABLED_TOKENS = frozenset({"", "none", "off", "disabled", "false"})
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _get_timezone(tz_name: str | None = None) -> datetime.tzinfo:
    name = (tz_name or os.getenv("CRAWLER_STOP_TIME_TZ") or DEFAULT_STOP_TIME_TZ).strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Tokyo":
            return datetime.timezone(datetime.timedelta(hours=9))
        raise


def parse_stop_time(raw: str | None) -> datetime.time | None:
    """Parse 'HH:MM' (24-hour) stop time. Returns None when disabled/empty."""
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if cleaned.lower() in _DISABLED_TOKENS:
        return None
    match = _HHMM_RE.match(cleaned)
    if not match:
        raise ValueError(f"Invalid stop time format '{raw}': expected HH:MM (00:00-23:59)")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid stop time value '{raw}': hour must be 0-23 and minute 0-59")
    return datetime.time(hour, minute)


def compute_stop_deadline(
    stop_time: datetime.time,
    now: datetime.datetime | None = None,
    tz_name: str | None = None,
) -> datetime.datetime:
    """Compute the next occurrence of stop_time in the configured timezone."""
    tz = _get_timezone(tz_name)
    current = now.astimezone(tz) if now is not None else datetime.datetime.now(tz)
    candidate = datetime.datetime.combine(current.date(), stop_time, tzinfo=tz)
    if current.time() >= stop_time:
        candidate += datetime.timedelta(days=1)
    return candidate


def seconds_until_stop(
    deadline: datetime.datetime,
    now: datetime.datetime | None = None,
) -> float:
    """Return remaining seconds until deadline (clamped to >= 0.0)."""
    current = now if now is not None else datetime.datetime.now(deadline.tzinfo)
    return max(0.0, (deadline - current).total_seconds())


def is_stop_time_reached(
    deadline: datetime.datetime | None,
    now: datetime.datetime | None = None,
) -> bool:
    """Return True when deadline is set and current time has reached or passed it."""
    if deadline is None:
        return False
    current = now if now is not None else datetime.datetime.now(deadline.tzinfo)
    return current >= deadline


def start_stop_time_watchdog(
    deadline: datetime.datetime,
    on_stop: Callable[[], None],
    check_interval_sec: float = 5.0,
) -> threading.Thread:
    """Start a daemon thread that calls on_stop() once deadline is reached."""
    interval = max(0.05, float(check_interval_sec))

    def _watch() -> None:
        while not is_stop_time_reached(deadline):
            remaining = seconds_until_stop(deadline)
            time.sleep(min(interval, max(0.05, remaining)))
        on_stop()

    thread = threading.Thread(target=_watch, name="crawler-stop-time-watchdog", daemon=True)
    thread.start()
    return thread
