# -*- coding: utf-8 -*-
"""
Issue #985: Cloud定期実行におけるポータルサイト（homes, athome）の完全除外および
件数規模順優先処理（Longest-Job-First）の検証ユニットテスト
"""
import os
from unittest.mock import patch

from package.utils.crawl_jobs import (
    PORTAL_COMPANIES,
    UNCRAWLED_COMPANIES,
    filter_crawl_jobs,
    is_cloud_environment,
)
from package.utils.crawler_scheduler import (
    calculate_job_priority,
    sort_jobs_by_priority,
)
from package.utils.task_distribution import distribute_jobs


def test_is_cloud_environment():
    """環境変数 IS_CLOUD または CRAWL_SKIP_PORTALS による Cloud 環境判定"""
    with patch.dict(os.environ, {}, clear=True):
        assert is_cloud_environment() is False

    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True):
        assert is_cloud_environment() is True

    with patch.dict(os.environ, {"IS_CLOUD": "1"}, clear=True):
        assert is_cloud_environment() is True

    with patch.dict(os.environ, {"CRAWL_SKIP_PORTALS": "true"}, clear=True):
        assert is_cloud_environment() is True

    with patch.dict(os.environ, {"IS_CLOUD": "false", "CRAWL_SKIP_PORTALS": "0"}, clear=True):
        assert is_cloud_environment() is False


def test_filter_crawl_jobs_with_cloud_env():
    """Cloud環境下では skip_portals が明示されなくても自動で除外されること"""
    # 1. ローカル環境 (IS_CLOUD 未定義): デフォルトで full 104 jobs
    with patch.dict(os.environ, {}, clear=True):
        jobs = filter_crawl_jobs()
        assert len(jobs) == 104
        assert any(c.lower() in PORTAL_COMPANIES for c, _ in jobs)

    # 2. Cloud環境 (IS_CLOUD=true): デフォルトで portal 8 jobs が除外され 96 jobs
    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True):
        jobs = filter_crawl_jobs()
        assert len(jobs) == 96
        assert not any(c.lower() in PORTAL_COMPANIES for c, _ in jobs)

    # 3. Cloud環境 + skip_uncrawled=True: 82 jobs
    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True):
        jobs = filter_crawl_jobs(skip_uncrawled=True)
        assert len(jobs) == 82
        assert not any(c.lower() in PORTAL_COMPANIES for c, _ in jobs)
        assert not any(c.lower() in UNCRAWLED_COMPANIES for c, _ in jobs)

    # 4. Cloud環境でも明示的に skip_portals=False を渡せば 104 jobs を返せる
    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True):
        jobs = filter_crawl_jobs(skip_portals=False)
        assert len(jobs) == 104
        assert any(c.lower() in PORTAL_COMPANIES for c, _ in jobs)


def test_calculate_job_priority():
    """主担当大手優先、主要仲介優先、その後マンション優先の3要素優先度タプル検証"""
    p_mitsui_mansion = calculate_job_priority("mitsui", "mansion", host_company="mitsui")
    p_mitsui_kodate = calculate_job_priority("mitsui", "kodate", host_company="mitsui")
    p_sumifu_mansion = calculate_job_priority("sumifu", "mansion", host_company="mitsui")
    p_smtrc_mansion = calculate_job_priority("smtrc", "mansion", host_company="mitsui")
    p_sekisui_mansion = calculate_job_priority("sekisui", "mansion", host_company="mitsui")
    p_sekisui_kodate = calculate_job_priority("sekisui", "kodate", host_company="mitsui")

    # 1. 主担当大手 × マンション: (1, 1, 1)
    assert p_mitsui_mansion == (1, 1, 1)
    # 2. 主担当大手 × その他種別: (1, 1, 0)
    assert p_mitsui_kodate == (1, 1, 0)
    # 3. 他大手 × マンション: (0, 1, 1)
    assert p_sumifu_mansion == (0, 1, 1)
    assert p_smtrc_mansion == (0, 1, 1)
    # 4. その他仲介 × マンション: (0, 0, 1)
    assert p_sekisui_mansion == (0, 0, 1)
    # 5. その他仲介 × その他種別: (0, 0, 0)
    assert p_sekisui_kodate == (0, 0, 0)

    # 優先順序: 主担当大手全種別 > 他主要大手×マンション > その他×マンション > その他×その他
    assert p_mitsui_kodate > p_sumifu_mansion
    assert p_sumifu_mansion > p_sekisui_mansion
    assert p_sekisui_mansion > p_sekisui_kodate


def test_sort_jobs_by_priority():
    """ジョブリストが「主担当大手 ➔ 大手仲介優先 ➔ マンション優先」の順にソートされること"""
    sample_jobs = [
        ("ietan", "tochi"),         # その他 × その他
        ("sekisui", "mansion"),     # その他 × マンション
        ("sumifu", "mansion"),      # 他社主要 × マンション
        ("mitsui", "kodate"),       # 主担当 × その他
        ("mitsui", "mansion"),      # 主担当 × マンション
    ]
    sorted_jobs = sort_jobs_by_priority(sample_jobs, host_company="mitsui")
    assert sorted_jobs == [
        ("mitsui", "mansion"),      # (1, 1, 1)
        ("mitsui", "kodate"),       # (1, 1, 0)
        ("sumifu", "mansion"),      # (0, 1, 1)
        ("sekisui", "mansion"),     # (0, 0, 1)
        ("ietan", "tochi"),         # (0, 0, 0)
    ]


def test_distribute_3_tasks():
    """三大仲介（三井・住友・東急）軸の3タスク決定論的分散検証"""
    jobs = filter_crawl_jobs(skip_portals=True, skip_uncrawled=True)
    assert len(jobs) == 82

    t0_jobs = distribute_jobs(jobs, task_index=0, task_count=3)
    t1_jobs = distribute_jobs(jobs, task_index=1, task_count=3)
    t2_jobs = distribute_jobs(jobs, task_index=2, task_count=3)

    # 合計件数が全ジョブと完全一致
    assert len(t0_jobs) + len(t1_jobs) + len(t2_jobs) == 82
    assert set(t0_jobs + t1_jobs + t2_jobs) == set(jobs)

    # 各タスクに三井、住友、東急が専任で割り当てられていること
    assert all(c == "mitsui" for c, _ in t0_jobs[:5])
    assert all(c == "sumifu" for c, _ in t1_jobs[:5])
    assert all(c == "tokyu" for c, _ in t2_jobs[:5])

    # 三井、住友、東急のジョブが他タスクに混入していないこと
    assert not any(c == "mitsui" for c, _ in t1_jobs)
    assert not any(c == "mitsui" for c, _ in t2_jobs)
    assert not any(c == "sumifu" for c, _ in t0_jobs)
    assert not any(c == "tokyu" for c, _ in t0_jobs)


def test_cli_skip_portals_default_in_cloud():
    """run_all_crawlers, run_pipeline, run_ml_pipeline の CLI デフォルト解決"""
    from scripts.ops.run_all_crawlers import parse_args as parse_all_args

    # 1. ローカル環境: 引数なし -> skip_portals is False
    with patch.dict(os.environ, {}, clear=True), patch("sys.argv", ["run_all_crawlers.py"]):
        args = parse_all_args()
        assert args.skip_portals is False

    # 2. Cloud環境: 引数なし -> skip_portals is True
    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True), patch("sys.argv", ["run_all_crawlers.py"]):
        args = parse_all_args()
        assert args.skip_portals is True

    # 3. Cloud環境: --no-skip-portals を指定 -> skip_portals is False
    with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=True), patch("sys.argv", ["run_all_crawlers.py", "--no-skip-portals"]):
        args = parse_all_args()
        assert args.skip_portals is False
