import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import time

from package.utils.crawler_watchdog import (
    touch_crawler_progress,
    get_progress_file_path,
    cleanup_crawler_progress,
    check_job_hung,
    _check_file_progress,
)
from package.utils.job_metrics import (
    export_job_metrics,
    read_job_metrics,
    mark_empty_result,
    reset_metrics,
)


def test_watchdog_touch_and_cleanup(tmp_path):
    with patch("package.utils.crawler_watchdog.get_progress_dir", return_value=tmp_path):
        p = get_progress_file_path("testcomp", "mansion")
        assert not p.exists()

        touch_crawler_progress("testcomp", "mansion")
        assert p.exists()
        mtime1 = p.stat().st_mtime

        time.sleep(0.01)
        touch_crawler_progress("testcomp", "mansion")
        mtime2 = p.stat().st_mtime
        assert mtime2 >= mtime1

        last_act, db_cnt = _check_file_progress("testcomp", "mansion", 0.0, 0)
        assert last_act == mtime2
        assert db_cnt == 1

        cleanup_crawler_progress("testcomp", "mansion")
        assert not p.exists()


def test_check_job_hung_respects_recent_touch():
    now = 1000.0
    start_time = 0.0
    threshold = 600.0

    # 1. 最後の活動が 900 秒前の場合はハング判定
    assert check_job_hung(last_activity_time=100.0, current_time=now, threshold_sec=threshold, start_time=start_time) is True

    # 2. 最後の活動が 100 秒前（最近 touch された）の場合は正常（ハングではない）
    assert check_job_hung(last_activity_time=900.0, current_time=now, threshold_sec=threshold, start_time=start_time) is False
