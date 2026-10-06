# -*- coding: utf-8 -*-
"""Issue #741: 必須項目欠損の厳格検査と保存後タグ付け共通化のテスト"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from package.utils.data_validator import (
    ERR_MISSING_ADDRESS,
    ERR_MISSING_AGE,
    ERR_MISSING_MADORI,
    ERR_MISSING_NAME,
    ERR_MISSING_TRAFFIC,
    PropertyDataValidator,
)


def _mansion(**over):
    base = {
        "propertyName": "テストマンション", "address": "東京都港区1-1", "traffic": "JR山手線 渋谷駅 徒歩5分",
        "station1": "渋谷", "price": 50000000, "senyuMenseki": 70.5, "madori": "3LDK", "kaisu": "5階",
        "chikunengetsu": datetime(2015, 5, 1, tzinfo=timezone.utc), "chikunengetsuStr": "",
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_complete_mansion_is_valid():
    ok, reasons = PropertyDataValidator.validate_property(_mansion(), "mansion")
    assert ok, reasons


@pytest.mark.parametrize("field,err", [
    ("propertyName", ERR_MISSING_NAME),
    ("address", ERR_MISSING_ADDRESS),
    ("madori", ERR_MISSING_MADORI),
])
def test_missing_required_field_detected(field, err):
    ok, reasons = PropertyDataValidator.validate_property(_mansion(**{field: ""}), "mansion")
    assert not ok
    assert err in reasons


def test_missing_traffic_detected_only_when_both_empty():
    _, reasons = PropertyDataValidator.validate_property(_mansion(traffic="", station1=""), "mansion")
    assert ERR_MISSING_TRAFFIC in reasons
    _, reasons = PropertyDataValidator.validate_property(_mansion(traffic="", station1="渋谷"), "mansion")
    assert ERR_MISSING_TRAFFIC not in reasons


def test_missing_age_detected():
    _, reasons = PropertyDataValidator.validate_property(
        _mansion(chikunengetsu=None, chikunengetsuStr=""), "mansion")
    assert ERR_MISSING_AGE in reasons


def test_tochi_does_not_require_madori_or_age():
    item = SimpleNamespace(
        propertyName="売地", address="東京都", traffic="駅 徒歩3分", price=30000000, tochiMenseki=150.0)
    ok, reasons = PropertyDataValidator.validate_property(item, "tochi")
    assert ok, reasons
