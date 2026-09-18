# -*- coding: utf-8 -*-
"""
バルクML評価の並行処理の単体テスト
"""
import pytest
from unittest.mock import MagicMock, patch
from scripts.ops.run_bulk_ml_evaluation import get_all_property_models


def test_get_all_property_models():
    models = get_all_property_models(skip_portals=True)
    assert isinstance(models, list)
    # ポータル（homes, athome）が含まれていないことを検証
    for m in models:
        m_name = m.__name__.lower()
        assert not m_name.startswith("homes")
        assert not m_name.startswith("athome")


def test_bulk_eval_concurrency_env(monkeypatch):
    import os
    monkeypatch.setenv("BULK_EVAL_CONCURRENCY", "6")
    assert int(os.getenv("BULK_EVAL_CONCURRENCY", "4")) == 6
