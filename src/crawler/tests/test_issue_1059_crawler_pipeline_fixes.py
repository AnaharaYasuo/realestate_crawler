"""Tests for Issue #1059: Cloud Run 4 tasks distribution, mtime watchdog, and parser resilience."""
import os
import time
import tempfile
import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup

from package.utils.task_distribution import (
    BIG_4_COMPANIES,
    distribute_jobs,
)
from package.utils.crawler_scheduler import (
    sort_jobs_by_priority,
)
from package.utils.crawler_watchdog import (
    check_job_hung,
    _update_single_job_progress,
    update_watchdog_progress,
    touch_crawler_progress,
    get_progress_file_path,
)
from package.parser.baseParser import SkipPropertyException, ListingEndedException
from package.parser.tokyuParser import TokyuMansionParser, TokyuTochiParser, TokyuKodateParser
from package.parser.rearieParser import RearieMansionParser
from package.models.sumai1 import Sumai1Tochi, Sumai1Investment


def test_big_4_companies_definition():
    """四大仲介会社が三井・住友・東急・野村で定義されていること"""
    assert BIG_4_COMPANIES == ["mitsui", "sumifu", "tokyu", "nomura"]


def test_4_tasks_distribution_each_has_host_company():
    """4台構成時、Task 0〜3 にそれぞれ四大仲介会社が1社ずつ割り当てられること"""
    all_jobs = [
        ("mitsui", "mansion"), ("mitsui", "kodate"), ("mitsui", "tochi"),
        ("sumifu", "mansion"), ("sumifu", "kodate"), ("sumifu", "tochi"),
        ("tokyu", "mansion"), ("tokyu", "kodate"), ("tokyu", "tochi"),
        ("nomura", "mansion"), ("nomura", "kodate"), ("nomura", "tochi"),
        ("daikyo", "mansion"), ("heim", "kodate"), ("afr", "tochi"), ("totate", "mansion"),
    ]
    task_0_jobs = distribute_jobs(all_jobs, task_index=0, task_count=4)
    task_1_jobs = distribute_jobs(all_jobs, task_index=1, task_count=4)
    task_2_jobs = distribute_jobs(all_jobs, task_index=2, task_count=4)
    task_3_jobs = distribute_jobs(all_jobs, task_index=3, task_count=4)

    # 各タスクに四大仲介会社が1社ずつ割り当てられていること
    assert any(company == "mitsui" for company, _ in task_0_jobs)
    assert not any(company in ["sumifu", "tokyu", "nomura"] for company, _ in task_0_jobs)

    assert any(company == "sumifu" for company, _ in task_1_jobs)
    assert not any(company in ["mitsui", "tokyu", "nomura"] for company, _ in task_1_jobs)

    assert any(company == "tokyu" for company, _ in task_2_jobs)
    assert not any(company in ["mitsui", "sumifu", "nomura"] for company, _ in task_2_jobs)

    assert any(company == "nomura" for company, _ in task_3_jobs)
    assert not any(company in ["mitsui", "sumifu", "tokyu"] for company, _ in task_3_jobs)


def test_sort_jobs_by_priority_host_major_types_first():
    """各タスクでホスト会社の件数が多い種別（マンション・戸建・土地）が先頭に優先ソートされること"""
    jobs = [
        ("daikyo", "mansion"),
        ("mitsui", "tochi"),
        ("mitsui", "invest_apartment"),
        ("mitsui", "mansion"),
        ("mitsui", "kodate"),
        ("heim", "kodate"),
    ]
    sorted_jobs = sort_jobs_by_priority(jobs, host_company="mitsui")
    # ホスト会社の主要3種別が最優先
    assert sorted_jobs[0] == ("mitsui", "mansion")
    assert sorted_jobs[1] == ("mitsui", "kodate")
    assert sorted_jobs[2] == ("mitsui", "tochi")


def test_watchdog_mtime_progress_update():
    """子プロセスが進捗ファイルを touch した場合、親プロセスが last_act を更新すること"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CRAWLER_PROGRESS_DIR"] = tmpdir
        company = "test_co"
        ptype = "mansion"

        # 1. 最初は進捗ファイルなし
        start_t = time.time() - 100.0
        job_info = (MagicMock(), company, ptype, start_t, MagicMock(), start_t, 0, 0.0)

        # 進捗更新実行
        updated = _update_single_job_progress(job_info, time.time(), count_fn=None, check_interval_sec=0.0)
        assert updated[5] == start_t  # last_act は未更新

        # 2. 子プロセスが進捗ファイルを touch
        touch_time = time.time()
        touch_crawler_progress(company, ptype)

        # 3. 再度進捗更新実行 -> last_act が touch_time 付近に更新されること
        updated_2 = _update_single_job_progress(job_info, time.time(), count_fn=None, check_interval_sec=0.0)
        assert updated_2[5] >= touch_time - 1.0


def test_check_job_hung_with_mtime_progress():
    """活動が進捗ファイルで記録されていれば、30分以上経過していてもハングと判定されないこと"""
    now = time.time()
    start_t = now - 2000.0  # 30分以上前
    last_act = now - 50.0   # 50秒前に活動

    # 閾値180秒の場合、50秒前ならハング判定されない
    is_hung = check_job_hung(last_activity_time=last_act, current_time=now, threshold_sec=180.0, prev_db_cnt=0, start_time=start_t)
    assert is_hung is False


def test_tokyu_non_investment_parsers_reject_fudosan_toushi():
    """東急の通常パーサー（マンション・戸建・土地）に投資用URLが混入した場合は安全にスキップされること"""
    invest_url = "https://www.livable.co.jp/fudosan-toushi/C2826X381/"
    
    mansion_parser = TokyuMansionParser()
    with pytest.raises(SkipPropertyException):
        mansion_parser._reject_non_property_url(invest_url)

    tochi_parser = TokyuTochiParser()
    with pytest.raises(SkipPropertyException):
        tochi_parser._reject_non_property_url(invest_url)

    kodate_parser = TokyuKodateParser()
    with pytest.raises(SkipPropertyException):
        kodate_parser._reject_non_property_url(invest_url)


def test_rearie_brand_only_top_redirect_detected():
    """リアリエで明示的な掲載終了文言がある場合に ListingEndedException が送出されること"""
    html = "<html><head><title>お探しの物件は見つかりませんでした - パナソニック ホームズ</title></head><body><h1>お探しの物件は見つかりませんでした</h1></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    parser = RearieMansionParser()
    
    item = parser.createEntity()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


def test_sumai1_models_allow_blank_fields():
    """すまい1の土地および投資用モデルで、欠落しやすいフィールドが blank=True でバリデーション通過すること"""
    # 土地モデル
    tochi = Sumai1Tochi()
    field_haba = tochi._meta.get_field("douroHaba")
    field_setsu = tochi._meta.get_field("setsumen")
    assert field_haba.blank is True
    assert field_setsu.blank is True

    # 投資用モデル
    invest = Sumai1Investment()
    field_soukosu = invest._meta.get_field("soukosu")
    assert field_soukosu.blank is True

def test_api_proc_base_touch_watchdog_progress():
    """ApiAsyncProcBase._touch_watchdog_progress touches progress file with lowercase names."""
    from package.api.mitsui import ParseMitsuiMansionDetailFuncAsync
    from package.utils.crawler_watchdog import cleanup_crawler_progress
    detail_obj = ParseMitsuiMansionDetailFuncAsync()
    p = get_progress_file_path("mitsui", "mansion")
    cleanup_crawler_progress("mitsui", "mansion")
    assert not p.exists()
    detail_obj._touch_watchdog_progress()
    assert p.exists()
    cleanup_crawler_progress("mitsui", "mansion")