import pytest
from package.utils import crawler_watchdog


def test_check_job_hung_initial_discovery_grace():
    """DBレコードがまだ0件のジョブはINITIAL_DISCOVERY_GRACE_SEC (1800秒) までハング終了させない"""
    start_t = 1000.0
    # 601秒経過（通常の600秒閾値を超えているが、初回ディスカバリー中の場合）
    now = start_t + 601.0
    last_act = start_t

    # prev_db_cnt == 0 かつ start_time 指定あり -> 猶予内なので False
    assert crawler_watchdog.check_job_hung(
        last_activity_time=last_act,
        current_time=now,
        threshold_sec=600.0,
        prev_db_cnt=0,
        start_time=start_t,
    ) is False

    # 1801秒経過 -> 初回猶予（1800秒）を超過したので True
    now_timeout = start_t + 1801.0
    assert crawler_watchdog.check_job_hung(
        last_activity_time=last_act,
        current_time=now_timeout,
        threshold_sec=600.0,
        prev_db_cnt=0,
        start_time=start_t,
    ) is True


def test_check_job_hung_with_db_records_normal_threshold():
    """一度でもDBレコードが記録されたジョブ（prev_db_cnt > 0）は通常の threshold_sec (600秒) でハング検知"""
    start_t = 1000.0
    last_act = 1500.0
    now = last_act + 601.0

    assert crawler_watchdog.check_job_hung(
        last_activity_time=last_act,
        current_time=now,
        threshold_sec=600.0,
        prev_db_cnt=10,
        start_time=start_t,
    ) is True

    # 599秒経過であればまだハングではない
    assert crawler_watchdog.check_job_hung(
        last_activity_time=last_act,
        current_time=last_act + 599.0,
        threshold_sec=600.0,
        prev_db_cnt=10,
        start_time=start_t,
    ) is False
