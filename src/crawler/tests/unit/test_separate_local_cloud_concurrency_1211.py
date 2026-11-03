"""Tests for Issue #1211: Separate Local and Cloud concurrency limit settings."""
import os
from unittest.mock import patch
import pytest

from package.utils.resource_limiter import get_resource_aware_concurrency
from package.api.api import _get_local_worker_concurrency
from package.api.adaptive_concurrency import AdaptiveConcurrencyController


def test_resource_aware_concurrency_local_environment():
    """ローカル環境(IS_CLOUD未設定)でLOCAL_*プレフィックスが優先されること"""
    env = {
        "IS_CLOUD": "",
        "LOCAL_CRAWLER_PARALLEL": "4",
        "CRAWLER_PARALLEL": "8",
        "CLOUD_CRAWLER_PARALLEL": "16",
        "LOCAL_CRAWLER_PLAYWRIGHT_PARALLEL": "2",
        "CRAWLER_PLAYWRIGHT_PARALLEL": "5",
        "CLOUD_CRAWLER_PLAYWRIGHT_PARALLEL": "7",
    }
    with patch.dict(os.environ, env, clear=True):
        p, pw, _ = get_resource_aware_concurrency()
        assert p == 4
        assert pw == 2


def test_resource_aware_concurrency_cloud_environment():
    """クラウド環境(IS_CLOUD=true)でCLOUD_*プレフィックスが優先されること"""
    env = {
        "IS_CLOUD": "true",
        "LOCAL_CRAWLER_PARALLEL": "4",
        "CRAWLER_PARALLEL": "8",
        "CLOUD_CRAWLER_PARALLEL": "16",
        "LOCAL_CRAWLER_PLAYWRIGHT_PARALLEL": "2",
        "CRAWLER_PLAYWRIGHT_PARALLEL": "5",
        "CLOUD_CRAWLER_PLAYWRIGHT_PARALLEL": "7",
    }
    with patch.dict(os.environ, env, clear=True):
        p, pw, _ = get_resource_aware_concurrency()
        assert p == 16
        assert pw == 7


def test_resource_aware_concurrency_fallback_to_common():
    """個別プレフィックスがない場合は共通のCRAWLER_*にフォールバックすること"""
    env = {
        "IS_CLOUD": "",
        "CRAWLER_PARALLEL": "6",
        "CRAWLER_PLAYWRIGHT_PARALLEL": "1",
    }
    with patch.dict(os.environ, env, clear=True):
        p, pw, _ = get_resource_aware_concurrency()
        assert p == 6
        assert pw == 1


def test_local_worker_concurrency_separation():
    """_get_local_worker_concurrency が環境ごとに個別設定を尊重すること"""
    # ローカル環境
    env_local = {
        "IS_CLOUD": "",
        "LOCAL_CRAWLER_LOCAL_WORKER_CONCURRENCY": "2",
        "CRAWLER_LOCAL_WORKER_CONCURRENCY": "5",
        "CLOUD_CRAWLER_LOCAL_WORKER_CONCURRENCY": "10",
    }
    with patch.dict(os.environ, env_local, clear=True):
        assert _get_local_worker_concurrency() == 2

    # クラウド環境
    env_cloud = {
        "IS_CLOUD": "true",
        "LOCAL_CRAWLER_LOCAL_WORKER_CONCURRENCY": "2",
        "CRAWLER_LOCAL_WORKER_CONCURRENCY": "5",
        "CLOUD_CRAWLER_LOCAL_WORKER_CONCURRENCY": "10",
    }
    with patch.dict(os.environ, env_cloud, clear=True):
        assert _get_local_worker_concurrency() == 10

    # 共通フォールバック
    env_fallback = {
        "IS_CLOUD": "",
        "CRAWLER_LOCAL_WORKER_CONCURRENCY": "4",
    }
    with patch.dict(os.environ, env_fallback, clear=True):
        assert _get_local_worker_concurrency() == 4


def test_detail_concurrency_separation():
    """calculate_detail_concurrency が環境ごとに個別設定を尊重すること"""
    # ローカル環境
    env_local = {
        "IS_CLOUD": "",
        "LOCAL_DETAIL_CONCURRENCY": "2",
        "DETAIL_CONCURRENCY": "5",
        "CLOUD_DETAIL_CONCURRENCY": "12",
    }
    with patch.dict(os.environ, env_local, clear=True):
        assert AdaptiveConcurrencyController.calculate_detail_concurrency() == 2

    # クラウド環境
    env_cloud = {
        "IS_CLOUD": "true",
        "LOCAL_DETAIL_CONCURRENCY": "2",
        "DETAIL_CONCURRENCY": "5",
        "CLOUD_DETAIL_CONCURRENCY": "12",
    }
    with patch.dict(os.environ, env_cloud, clear=True):
        assert AdaptiveConcurrencyController.calculate_detail_concurrency() == 12

    # ローカルでLOCAL未設定・DETAIL_CONCURRENCY設定時
    env_local_fallback = {
        "IS_CLOUD": "",
        "DETAIL_CONCURRENCY": "3",
        "CLOUD_DETAIL_CONCURRENCY": "12",
    }
    with patch.dict(os.environ, env_local_fallback, clear=True):
        assert AdaptiveConcurrencyController.calculate_detail_concurrency() == 3
