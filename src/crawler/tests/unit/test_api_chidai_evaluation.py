# -*- coding: utf-8 -*-
"""
APIレイヤーにおける地代負債（PropertyEvaluation用）算出ロジックの単体テスト
"""
from decimal import Decimal
from unittest.mock import MagicMock

from package.utils.converter import parse_chidai


def compute_chidai_and_liability(item):
    """api.py ParseDetailPageAsyncBase._create_or_update_evaluation 内の地代負債算出ロジックと同等"""
    chidai_val = getattr(item, "chidai", None)
    if chidai_val is None and getattr(item, "chidaiStr", None):
        chidai_val = parse_chidai(item.chidaiStr)
    monthly_rent = int(chidai_val) if chidai_val and int(chidai_val) > 0 else None
    liability = Decimal(int((monthly_rent * 12.0) / 10000.0 / 0.05)) if monthly_rent else None
    return monthly_rent, liability


def test_api_chidai_calculation_with_direct_chidai():
    """item.chidai に数値が設定されている場合、月額および負債現在価値が正確に算出されること"""
    mock_item = MagicMock()
    mock_item.chidai = 20000
    mock_item.chidaiStr = "20,000円"

    monthly_rent, liability = compute_chidai_and_liability(mock_item)
    assert monthly_rent == 20000
    # 20,000 * 12 = 240,000円 -> 24.0万円 / 0.05 = 480万円
    assert liability == Decimal("480")


def test_api_chidai_calculation_with_chidaistr_fallback():
    """item.chidai が None で chidaiStr のみ存在する場合、自動パースされて算出されること"""
    mock_item = MagicMock()
    mock_item.chidai = None
    mock_item.chidaiStr = "月額3万円"

    monthly_rent, liability = compute_chidai_and_liability(mock_item)
    assert monthly_rent == 30000
    # 30,000 * 12 = 360,000円 -> 36.0万円 / 0.05 = 720万円
    assert liability == Decimal("720")


def test_api_chidai_calculation_missing():
    """地代情報がない場合、None として安全にフォールバックすること"""
    mock_item = MagicMock()
    mock_item.chidai = None
    mock_item.chidaiStr = None

    monthly_rent, liability = compute_chidai_and_liability(mock_item)
    assert monthly_rent is None
    assert liability is None
