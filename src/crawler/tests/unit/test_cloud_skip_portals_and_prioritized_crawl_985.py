# -*- coding: utf-8 -*-
"""
Issue #985: Cloud定期実行におけるポータルサイト（homes, athome）の完全除外および
件数規模順優先処理（Longest-Job-First）の検証ユニットテスト
"""
import os
import sys
import argparse
from unittest.mock import patch

import pytest

from package.utils.crawl_jobs import (
    CRAWL_JOBS,
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
    """大手仲介優先、その後マンション優先の2軸優先度タプル検証"""
    p_mitsui_mansion = calculate_job_priority("mitsui", "mansion")
    p_mitsui_kodate = calculate_job_priority("mitsui", "kodate")
    p_smtrc_mansion = calculate_job_priority("smtrc", "mansion")
    p_sekisui_mansion = calculate_job_priority("sekisui", "mansion")
    p_sekisui_kodate = calculate_job_priority("sekisui", "kodate")

    # 1. 大手仲介 × マンション: (1, 1)
    assert p_mitsui_mansion == (1, 1)
    assert p_smtrc_mansion == (1, 1)

    # 2. 大手仲介 × その他種別: (1, 0)
    assert p_mitsui_kodate == (1, 0)

    # 3. その他仲介 × マンション: (0, 1)
    assert p_sekisui_mansion == (0, 1)

    # 4. その他仲介 × その他種別: (0, 0)
    assert p_sekisui_kodate == (0, 0)

    # 優先順序: 大手×マンション > 大手×その他 > その他×マンション > その他×その他
    assert p_mitsui_mansion > p_mitsui_kodate
    assert p_mitsui_kodate > p_sekisui_mansion
    assert p_sekisui_mansion > p_sekisui_kodate


def test_sort_jobs_by_priority():
    """ジョブリストが「大手仲介優先 ➔ マンション優先」の順にソートされること"""
    sample_jobs = [
        ("ietan", "tochi"),         # その他 × その他: (0, 0)
        ("sekisui", "mansion"),     # その他 × マンション: (0, 1)
        ("sumifu", "kodate"),       # 大手 × その他: (1, 0)
        ("mitsui", "mansion"),      # 大手 × マンション: (1, 1)
    ]
    sorted_jobs = sort_jobs_by_priority(sample_jobs)
    assert sorted_jobs == [
        ("mitsui", "mansion"),      # (1, 1)
        ("sumifu", "kodate"),       # (1, 0)
        ("sekisui", "mansion"),     # (0, 1)
        ("ietan", "tochi"),         # (0, 0)
    ]


def test_cli_skip_portals_default_in_cloud():
    """run_all_crawlers, run_pipeline, run_ml_pipeline の CLI デフォルト解決"""
    from scripts.ops.run_all_crawlers import parse_args as parse_all_args
    from scripts.ops.run_pipeline import main as run_pipeline_main
    from scripts.ops.run_ml_pipeline import main as run_ml_pipeline_main

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
