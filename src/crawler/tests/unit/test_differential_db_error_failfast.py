# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError
from package.api.differential import _process_differential_chunk, ListItem


@pytest.mark.asyncio
async def test_process_differential_chunk_db_error_failfast():
    """原則1.1: DB接続障害時は全件クロールへフォールバックせず例外を送出して停止すること"""
    chunk = [ListItem(url="https://example.com/prop1", price=50000000)]
    mock_model = MagicMock()

    # DB クエリが OperationalError (2002 接続拒否) を送出するシチュエーション
    with patch("package.api.differential._query_existing_records_sync", side_effect=OperationalError(2002, "Can't connect to server on '127.0.0.1'")):
        with pytest.raises(OperationalError) as exc_info:
            await _process_differential_chunk(chunk, mock_model, now=None, ttl_days=30)
        assert 2002 in exc_info.value.args or "Can't connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_process_differential_chunk_non_db_error_fallback():
    """DB接続エラー以外の軽微な例外時は全件クロールへフォールバックすること"""
    chunk = [ListItem(url="https://example.com/prop1", price=50000000)]
    mock_model = MagicMock()

    with patch("package.api.differential._query_existing_records_sync", side_effect=ValueError("bad data")):
        to_fetch, to_skip = await _process_differential_chunk(chunk, mock_model, now=None, ttl_days=30)
        assert to_fetch == ["https://example.com/prop1"]
        assert to_skip == []
