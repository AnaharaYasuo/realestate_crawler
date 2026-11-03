# -*- coding: utf-8 -*-
"""
バルクML評価の対象抽出および分析日時フィルタリングのユニットテスト
"""
import datetime
from unittest.mock import MagicMock
from django.utils import timezone
from package.ml.evaluation.targets import _should_skip_item


class TestShouldSkipItem:
    """_should_skip_item の条件判定テスト"""

    def test_skip_when_unpublished(self):
        eval_rec = MagicMock()
        eval_rec.is_published = False
        eval_rec.needs_recrawl = False
        assert _should_skip_item(eval_rec, force=False) is True
        assert _should_skip_item(eval_rec, force=True) is True

    def test_skip_when_needs_recrawl(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = True
        assert _should_skip_item(eval_rec, force=False) is True
        assert _should_skip_item(eval_rec, force=True) is True

    def test_force_reevaluates(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.first_stage_predicted_price = 50000000
        assert _should_skip_item(eval_rec, force=True) is False

    def test_default_skips_if_predicted_price_exists(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.first_stage_predicted_price = 50000000
        assert _should_skip_item(eval_rec, force=False) is True

    def test_default_does_not_skip_if_predicted_price_none(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.first_stage_predicted_price = None
        assert _should_skip_item(eval_rec, force=False) is False

    def test_reevaluate_before_with_none_eval(self):
        threshold = timezone.make_aware(datetime.datetime(2026, 11, 3, 0, 0, 0))
        assert _should_skip_item(None, force=False, reevaluate_before=threshold) is False

    def test_reevaluate_before_with_none_analyzed_at(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.analyzed_at = None
        threshold = timezone.make_aware(datetime.datetime(2026, 11, 3, 0, 0, 0))
        # analyzed_at が None なら指定日より古いとみなして再処理対象（スキップしない）
        assert _should_skip_item(eval_rec, force=False, reevaluate_before=threshold) is False

    def test_reevaluate_before_with_older_analyzed_at(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.analyzed_at = timezone.make_aware(datetime.datetime(2026, 11, 2, 23, 59, 59))
        threshold = timezone.make_aware(datetime.datetime(2026, 11, 3, 0, 0, 0))
        # 閾値より古いので再処理対象（スキップしない）
        assert _should_skip_item(eval_rec, force=False, reevaluate_before=threshold) is False

    def test_reevaluate_before_with_newer_analyzed_at(self):
        eval_rec = MagicMock()
        eval_rec.is_published = True
        eval_rec.needs_recrawl = False
        eval_rec.analyzed_at = timezone.make_aware(datetime.datetime(2026, 11, 3, 10, 0, 0))
        threshold = timezone.make_aware(datetime.datetime(2026, 11, 3, 0, 0, 0))
        # 閾値以降に既に分析済みなのでスキップ
        assert _should_skip_item(eval_rec, force=False, reevaluate_before=threshold) is True
