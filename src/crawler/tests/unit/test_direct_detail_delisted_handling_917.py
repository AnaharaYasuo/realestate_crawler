# -*- coding: utf-8 -*-
"""
Issue #917: 対象物件URL直接詳細巡回および公開終了レコード永続化テスト
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from package.api.api import ParseDetailPageAsyncBase
from scripts.maintenance.recrawl_anomalies import (
    TargetPropertyRef,
    fetch_assigned_targets,
)


class ConcreteDirectDetailProc(ParseDetailPageAsyncBase):
    def _generateParser(self):
        parser = MagicMock()
        parser.company = "nomura"
        parser.property_type = "kodate"
        entity = MagicMock()
        entity.__class__ = MagicMock()
        parser.createEntity.return_value = entity
        return parser

    def _getLocalPararellLimit(self):
        return 3

    def _getCloudPararellLimit(self):
        return 3

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return ""


@pytest.mark.asyncio
async def test_handle_skipped_property_creates_new_evaluation_when_missing():
    """PropertyEvaluation が未登録の物件でも、公開終了検知時に新規作成して公開終了(is_published=False)が保存されること"""
    proc = ConcreteDirectDetailProc()
    proc.url = "https://www.nomu.com/house/id/TEST_NEW_DELISTED/"

    # PropertyEvaluation が DB に存在しない状態
    with patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter, \
         patch("package.utils.url_matcher.UrlMatcher.find_match_in_queryset", return_value=None), \
         patch("package.models.evaluation.PropertyEvaluation.objects.create") as mock_create:

        mock_filter.return_value.first.return_value = None

        await proc._handle_skipped_property()

        mock_create.assert_called_once()
        kwargs = mock_create.call_args[1]
        assert kwargs["property_url"] == proc.url
        assert kwargs["is_published"] is False
        assert kwargs["delisted_at"] is not None
        assert kwargs["company"] == "nomura"
        assert kwargs["property_type"] == "kodate"


@pytest.mark.asyncio
async def test_handle_skipped_property_updates_existing_evaluation():
    """既存の PropertyEvaluation が存在する場合、is_published=False, delisted_at が正しく更新されること"""
    proc = ConcreteDirectDetailProc()
    proc.url = "https://www.nomu.com/house/id/TEST_EXISTING_DELISTED/"

    mock_eval = MagicMock()
    mock_eval.is_published = True
    mock_eval.needs_parser_fix = False

    with patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter, \
         patch("package.utils.url_matcher.UrlMatcher.find_match_in_queryset", return_value=None):

        mock_filter.return_value.first.return_value = mock_eval

        await proc._handle_skipped_property()

        assert mock_eval.is_published is False
        assert mock_eval.delisted_at is not None
        mock_eval.save.assert_called_once()


def test_fetch_assigned_targets_with_direct_urls():
    """URL直接指定時にタスクModulo分割およびリミットが正常に機能すること"""
    urls = [f"https://www.nomu.com/house/id/{i}/" for i in range(10)]

    targets_all = fetch_assigned_targets(task_index=None, task_count=1, urls=urls)
    assert len(targets_all) == 10
    assert all(isinstance(t, TargetPropertyRef) for t in targets_all)

    # Modulo 分割
    targets_task0 = fetch_assigned_targets(task_index=0, task_count=2, urls=urls)
    targets_task1 = fetch_assigned_targets(task_index=1, task_count=2, urls=urls)
    assert len(targets_task0) == 5
    assert len(targets_task1) == 5
    assert {t.property_id for t in targets_task0}.isdisjoint({t.property_id for t in targets_task1})

    # Limit
    targets_limited = fetch_assigned_targets(task_index=None, task_count=1, limit=3, urls=urls)
    assert len(targets_limited) == 3


@pytest.mark.asyncio
async def test_recrawl_single_url_returns_delisted():
    """AnomalyDetailRunner 経由で公開終了物件を再巡回した際、delisted ステータスが返されること"""
    from scripts.maintenance.recrawl_anomalies import _recrawl_single_url, CircuitBreakerState

    sem = MagicMock()
    sem.__aenter__ = AsyncMock()
    sem.__aexit__ = AsyncMock()
    cb = CircuitBreakerState()

    target = TargetPropertyRef("https://www.nomu.com/house/id/TEST_URL/")

    mock_eval = MagicMock()
    mock_eval.is_published = False

    with patch("scripts.maintenance.recrawl_anomalies.AnomalyDetailRunner.run", new_callable=AsyncMock) as mock_run, \
         patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter:

        mock_run.return_value = None  # ListingEnded で item は None
        mock_filter.return_value.first.return_value = mock_eval

        outcome = await _recrawl_single_url(sem, target, cb)
        assert outcome == "delisted"
        assert cb.consecutive_failures == 0
