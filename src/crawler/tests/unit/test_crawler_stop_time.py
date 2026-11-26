"""Unit tests for crawler stop-time (cutoff) utility and CLI integration (Issue #1845)."""
from __future__ import annotations

import datetime
import threading
from zoneinfo import ZoneInfo

import pytest

from package.utils.stop_time import (
    DEFAULT_DAILY_STOP_TIME,
    compute_stop_deadline,
    is_stop_time_reached,
    parse_stop_time,
    seconds_until_stop,
    start_stop_time_watchdog,
)

JST = ZoneInfo("Asia/Tokyo")


def test_parse_stop_time_valid_values():
    assert parse_stop_time("11:30") == datetime.time(11, 30)
    assert parse_stop_time("00:00") == datetime.time(0, 0)
    assert parse_stop_time("23:59") == datetime.time(23, 59)
    assert parse_stop_time(" 09:05 ") == datetime.time(9, 5)


@pytest.mark.parametrize("raw", [None, "", "   ", "none", "NONE", "off", "disabled"])
def test_parse_stop_time_disabled_values(raw):
    assert parse_stop_time(raw) is None


@pytest.mark.parametrize("raw", ["24:00", "25:10", "11:60", "abc", "1130", "-1:00"])
def test_parse_stop_time_invalid_raises(raw):
    with pytest.raises(ValueError):
        parse_stop_time(raw)


def test_default_daily_stop_time_is_1130():
    assert DEFAULT_DAILY_STOP_TIME == "11:30"
    assert parse_stop_time(DEFAULT_DAILY_STOP_TIME) == datetime.time(11, 30)


def test_compute_stop_deadline_same_day_when_before_cutoff():
    now = datetime.datetime(2026, 11, 26, 9, 30, 0, tzinfo=JST)
    deadline = compute_stop_deadline(datetime.time(11, 30), now=now)
    assert deadline == datetime.datetime(2026, 11, 26, 11, 30, 0, tzinfo=JST)
    assert seconds_until_stop(deadline, now=now) == pytest.approx(7200.0)


def test_compute_stop_deadline_next_day_when_at_or_after_cutoff():
    now_late = datetime.datetime(2026, 11, 25, 23, 0, 0, tzinfo=JST)
    deadline = compute_stop_deadline(datetime.time(11, 30), now=now_late)
    assert deadline == datetime.datetime(2026, 11, 26, 11, 30, 0, tzinfo=JST)

    now_exact = datetime.datetime(2026, 11, 26, 11, 30, 0, tzinfo=JST)
    deadline_exact = compute_stop_deadline(datetime.time(11, 30), now=now_exact)
    assert deadline_exact == datetime.datetime(2026, 11, 27, 11, 30, 0, tzinfo=JST)


def test_is_stop_time_reached():
    deadline = datetime.datetime(2026, 11, 26, 11, 30, 0, tzinfo=JST)
    assert is_stop_time_reached(None) is False
    assert is_stop_time_reached(deadline, now=datetime.datetime(2026, 11, 26, 11, 29, 59, tzinfo=JST)) is False
    assert is_stop_time_reached(deadline, now=datetime.datetime(2026, 11, 26, 11, 30, 0, tzinfo=JST)) is True
    assert is_stop_time_reached(deadline, now=datetime.datetime(2026, 11, 26, 11, 35, 0, tzinfo=JST)) is True


def test_start_stop_time_watchdog_invokes_callback_when_reached():
    triggered = threading.Event()
    past_deadline = datetime.datetime.now(JST) - datetime.timedelta(seconds=1)
    t = start_stop_time_watchdog(
        past_deadline,
        on_stop=triggered.set,
        check_interval_sec=0.05,
    )
    assert triggered.wait(timeout=2.0) is True
    t.join(timeout=1.0)
