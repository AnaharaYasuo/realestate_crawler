# -*- coding: utf-8 -*-
"""
Issue #773: 再クローリング時公開終了物件の不整合フラグ維持およびML学習データからの不整合物件除外テスト
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from package.models.evaluation import PropertyEvaluation


@pytest.mark.asyncio
async def test_crawler_detail_preserves_needs_parser_fix_on_delisted():
    """
    再クローリング時、SkipPropertyException等でスキップ/公開終了判定された際、
    既存の needs_parser_fix=True が False に初期化されず維持されることを検証 (Issue #773)
    """
    from package.api.api import ParseDetailPageAsyncBase
    from package.parser.baseParser import ListingEndedException

    class TestDetailProc(ParseDetailPageAsyncBase):
        def __init__(self, target_url, parser_mock):
            self._mock_parser = parser_mock
            super().__init__()
            self.url = target_url

        def _generateParser(self):
            return self._mock_parser

        def _getLocalPararellLimit(self):
            return 1

        def _getCloudPararellLimit(self):
            return 1

        def _getTimeOutSecond(self):
            return 5

        def _getApiKey(self):
            return ""

    test_url = "https://example.com/test_property_delisted_773"

    # 事前に needs_parser_fix=True のレコードが存在するモック
    existing_rec = MagicMock(spec=PropertyEvaluation)
    existing_rec.property_url = test_url
    existing_rec.is_published = True
    existing_rec.needs_parser_fix = True
    existing_rec.needs_recrawl = True
    existing_rec.save = MagicMock()

    with patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter:
        mock_filter.return_value.first.return_value = existing_rec

        parser_mock = MagicMock()
        parser_mock.parsePropertyDetailPage = AsyncMock(side_effect=ListingEndedException("Listing Ended"))
        parser_mock.createEntity = MagicMock()

        proc = TestDetailProc(test_url, parser_mock)
        session = MagicMock()
        item = await proc._treatPage(session)

        assert item is None
        # is_published は False, needs_recrawl は False になる
        assert existing_rec.is_published is False
        assert existing_rec.needs_recrawl is False
        # 最重要: needs_parser_fix は True のまま維持されていること！
        assert existing_rec.needs_parser_fix is True
        assert existing_rec.delisted_at is not None
        assert existing_rec.save.called


def test_data_loader_excludes_invalid_properties():
    """
    data_loader.py において、needs_parser_fix=True または data_quality_issue 設定物件が
    除外キャッシュに収集され、stream_training_features でスキップされることを検証 (Issue #773)
    """
    from package.ml.training.data_loader import (
        get_evaluation_and_duplicate_caches,
        _collect_lightweight_records_for_ptype,
    )

    # 1. キャッシュ収集の検証
    mock_evals = [
        ("https://example.com/normal", 4.0, 4.0),
        ("https://example.com/invalid_flag", 3.0, 3.0),
        ("https://example.com/invalid_issue", 3.0, 3.0),
    ]

    mock_invalid_qs = [
        "https://example.com/invalid_flag",
        "https://example.com/invalid_issue",
    ]

    mock_duplicate_qs = [
        "https://example.com/dup1",
    ]

    with patch("package.models.evaluation.PropertyEvaluation.objects.all") as mock_all, \
         patch("package.models.evaluation.PropertyEvaluation.objects.filter") as mock_filter:

        mock_all.return_value.values_list.return_value = mock_evals

        # filter 呼出の分岐: duplicate_of__isnull=False と needs_parser_fix=True / data_quality_issue
        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if "duplicate_of__isnull" in kwargs:
                m.values_list.return_value = mock_duplicate_qs
            else:
                m.values_list.return_value = mock_invalid_qs
            return m

        mock_filter.side_effect = filter_side_effect

        eval_map, excluded_urls = get_evaluation_and_duplicate_caches()

        assert "https://example.com/normal" in eval_map
        assert "https://example.com/dup1" in excluded_urls
        assert "https://example.com/invalid_flag" in excluded_urls
        assert "https://example.com/invalid_issue" in excluded_urls

    # 2. _collect_lightweight_records_for_ptype におけるスキップ検証
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    mock_model.objects.order_by.return_value.values_list.return_value = [
        (1, 50000000, "https://example.com/normal"),
        (2, 40000000, "https://example.com/invalid_flag"),
        (3, 30000000, "https://example.com/dup1"),
    ]

    models_list = [("mitsui", mock_model)]
    records = _collect_lightweight_records_for_ptype(models_list, excluded_urls)

    assert len(records) == 1
    assert records[0][2] == 1  # pk 1 のみ
    assert records[0][4] == "https://example.com/normal"
