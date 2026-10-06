# -*- coding: utf-8 -*-
"""
Issue #735: needs_parser_fix 物件の分散再クローリングおよび掲載終了連携テスト
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from package.parser.baseParser import ListingEndedException
from package.api.api import ParseDetailPageAsyncBase


class ConcreteDetailProc(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MagicMock()

    def _getLocalPararellLimit(self):
        return 3

    def _getCloudPararellLimit(self):
        return 3

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return ""


@pytest.mark.asyncio
async def test_detail_async_listing_ended_marks_delisted():
    """DetailAsync で ListingEndedException 発生時、PropertyEvaluation が非公開化されること"""
    proc = ConcreteDetailProc()
    proc.url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/TEST_DELISTED/"

    # parser.parsePropertyDetailPage が ListingEndedException を投げるモック
    proc.parser.parsePropertyDetailPage = AsyncMock(side_effect=ListingEndedException("Listing ended"))

    # PropertyEvaluation のモック
    mock_eval = MagicMock()
    mock_eval.is_published = True
    mock_eval.needs_parser_fix = True

    with patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter:
        mock_filter.return_value.first.return_value = mock_eval
        session = MagicMock()
        item = await proc._treatPage(session)

        assert item is None
        assert mock_eval.is_published is False
        assert mock_eval.delisted_at is not None
        assert mock_eval.needs_parser_fix is False
        mock_eval.save.assert_called_once()


def test_recrawl_modulo_distribution():
    """task-count と task-index による Modulo 分割が決定論的かつ重複なく行われること"""
    from scripts.maintenance.recrawl_anomalies import filter_targets_by_task

    class DummyEval:
        def __init__(self, property_id):
            self.property_id = property_id

    records = [DummyEval(i) for i in range(100)]

    task_count = 8
    assigned_tasks = {}
    for task_index in range(task_count):
        subset = filter_targets_by_task(records, task_index=task_index, task_count=task_count)
        assigned_tasks[task_index] = set(subset)
        # 各タスクの要素は property_id % task_count == task_index であること
        for item in subset:
            assert item.property_id % task_count == task_index

    # 全タスクの和集合が元の集合と一致し、互いに素であること
    all_assigned = set()
    for task_index, subset in assigned_tasks.items():
        assert len(all_assigned.intersection(subset)) == 0
        all_assigned.update(subset)
    assert len(all_assigned) == 100
