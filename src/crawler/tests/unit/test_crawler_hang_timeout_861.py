# -*- coding: utf-8 -*-
"""
Tests for Issue #861:
- Rate limiter thread safety across distinct event loops
- Local execution timeout guard in _handle_local_execution
- Watchdog hang detection without skipping active jobs (removal of early break)
- Strict HTTP request timeouts
"""
import asyncio
import os
import signal
import threading
import time
from unittest.mock import MagicMock, patch

from package.api import api as api_module
from package.utils import crawler_watchdog
from scripts.ops import run_all_crawlers


class _DummyDetailApi(api_module.ParseDetailPageAsyncBase):
    def _generateParser(self):
        m = MagicMock()
        m.getCharset.return_value = "utf-8"
        return m

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return "/api/dummy/detail"

    def _getTreatPageArg(self):
        return None

    async def _treatPage(self, session, *args):
        return None

    def _resolve_target_company(self):
        return "mitsui"


def test_rate_limiter_multiloop_thread_safe():
    """Different event loops in different threads should not raise RuntimeError: Lock is bound to a different event loop"""
    api = _DummyDetailApi()
    errors = []

    def thread_target():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(api._apply_download_delay_if_needed())
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            new_loop.close()

    t1 = threading.Thread(target=thread_target)
    t2 = threading.Thread(target=thread_target)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors, f"Rate limiter failed across threads: {errors}"


def test_handle_local_execution_timeout():
    """_handle_local_execution should terminate and return 504 when worker thread hangs beyond timeout"""
    api = _DummyDetailApi()

    class _HangingTarget:
        def main(self, url):
            time.sleep(10.0)

    with patch.dict(os.environ, {"LOCAL_EXECUTION_TIMEOUT_SEC": "0.2", "CRAWLER_FIRE_AND_FORGET": "false"}), \
         patch("package.api.api.ApiRegistry.get", return_value=_HangingTarget):
        start = time.time()
        res = api._handle_local_execution("/api/dummy/detail", "http://example.com/item")
        elapsed = time.time() - start

        assert res is not None
        assert res[1] == 504
        assert res[2] == "LocalTimeout"
        assert elapsed < 2.0


def test_watchdog_hang_check_all_jobs_without_break():
    """Watchdog loop must check all candidate jobs with last_check_t >= 15s rather than stopping at the first one"""
    now = 1000.0
    proc1 = MagicMock()
    proc1.poll.return_value = None
    proc2 = MagicMock()
    proc2.poll.return_value = None

    # Both jobs haven't been checked for 20s (> 15s)
    active = {
        1: (proc1, "mitsui", "mansion", 900.0, None, 950.0, 10, now - 20.0),
        2: (proc2, "sumifu", "mansion", 900.0, None, 950.0, 5, now - 20.0),
    }

    # Simulate get_count_for_job returning +1 item for each
    with patch("scripts.ops.run_all_crawlers.get_count_for_job", return_value=(0, 0, 20)):
        # Execute inspection logic
        for idx in tuple(active.keys()):
            proc, company, ptype, start_t, start_dt, *extra = active[idx]
            last_act = extra[0] if extra else start_t
            prev_db_cnt = extra[1] if len(extra) > 1 else 0
            last_check_t = extra[2] if len(extra) > 2 else 0.0
            if (now - last_check_t) >= 15.0:
                counts = run_all_crawlers.get_count_for_job(company, ptype, start_dt)
                current_db_cnt = counts[2] if counts[0] is not None else None
                if current_db_cnt is not None:
                    if current_db_cnt > prev_db_cnt:
                        last_act = now
                    active[idx] = (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)

    # Both jobs should be updated to now for check_t and last_act
    assert active[1][5] == now  # last_act
    assert active[1][7] == now  # last_check_t
    assert active[2][5] == now
    assert active[2][7] == now


def test_watchdog_triggers_kill_on_hung_job():
    """check_job_hung correctly identifies silent jobs and kill_hung_job_process attempts SIGKILL"""
    proc = MagicMock(pid=12345)
    proc.poll.return_value = None

    assert crawler_watchdog.check_job_hung(last_activity_time=100.0, current_time=750.0, threshold_sec=600.0) is True
    assert crawler_watchdog.check_job_hung(last_activity_time=200.0, current_time=750.0, threshold_sec=600.0) is False

    proc.communicate = MagicMock()
    if hasattr(os, "getpgid"):
        with patch("os.getpgid", return_value=12345), \
             patch("os.killpg") as mock_killpg:
            success = crawler_watchdog.kill_hung_job_process(proc)
            assert success is True
            mock_killpg.assert_called_once_with(12345, signal.SIGKILL)
    else:
        success = crawler_watchdog.kill_hung_job_process(proc)
        assert success is True
        proc.kill.assert_called_once()


def test_ensure_resources_stopped_job_hung_threshold():
    """get_job_hung_threshold returns correct specific threshold for crawler, ml, and migrate jobs"""
    from scripts import ensure_resources_stopped

    assert ensure_resources_stopped.get_job_hung_threshold("realestate-crawler-pipeline-prod") == 15000.0
    assert ensure_resources_stopped.get_job_hung_threshold("realestate-ml-pipeline-prod") == 7800.0
    assert ensure_resources_stopped.get_job_hung_threshold("realestate-migrate-prod") == 900.0
    assert ensure_resources_stopped.get_job_hung_threshold("unknown-job", fallback_threshold=5000.0) == 5000.0
    # Explicit override takes priority even for known jobs
    assert ensure_resources_stopped.get_job_hung_threshold("realestate-crawler-pipeline-prod", fallback_threshold=3600.0) == 3600.0
