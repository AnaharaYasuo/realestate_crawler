# -*- coding: utf-8 -*-
"""
Issue #692: クローラー詳細取得の非同期並行化、差分TTL 30日化、およびタイムアウト5時間枠延長のテスト
"""
import os
import inspect
import asyncio
from unittest.mock import patch, MagicMock
import pytest

from package.api import api as api_module
from package.api import differential as diff_module
from scripts.ops import run_all_crawlers, run_pipeline
from scripts import ensure_resources_stopped


def test_differential_ttl_default_is_30_days():
    """基準3: DIFFERENTIAL_TTL_DAYS のデフォルトが 30 日であること"""
    code = inspect.getsource(api_module.ParseMiddlePageAsyncBase._callApi)
    assert '"30"' in code or "30" in code
    sig = inspect.signature(diff_module.filter_differential_items)
    assert sig.parameters["ttl_days"].default == 30


def test_run_all_crawlers_default_parallel_is_safe():
    """基準2: DB保護のためデフォルト並行度が 6 に抑制されていること"""
    code = inspect.getsource(run_all_crawlers.parse_args)
    assert "default_parallel = 6" in code


def test_run_all_crawlers_timeout_is_five_hours():
    """基準4: 1ジョブのタイムアウトが 18000s (5h) に設定されていること"""
    assert run_all_crawlers.timeout_sec == 18000


def test_run_pipeline_default_timeout_is_five_hours():
    """基準4: run_pipeline の DEFAULT_TIMEOUT_SEC が 18000.0 であること"""
    assert run_pipeline.DEFAULT_TIMEOUT_SEC == 18000.0


def test_ensure_resources_stopped_hung_threshold_is_five_hours_plus_grace():
    """基準4: Safety-Net のハング判定閾値が 18600.0s (18000s + 600s) であること"""
    assert ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC == 18600.0


@pytest.mark.asyncio
async def test_handle_local_execution_async_concurrent():
    """基準1: _handle_local_execution が同期シグネチャを保持しつつ asyncio.to_thread で並行実行可能であること"""
    proc = api_module.ApiAsyncProcBase()
    assert not inspect.iscoroutinefunction(proc._handle_local_execution)
    with patch("package.api.api.ApiRegistry.get", return_value=None):
        res = await asyncio.to_thread(proc._handle_local_execution, "http://localhost/test", "http://example.com/item1")
        assert res is None

