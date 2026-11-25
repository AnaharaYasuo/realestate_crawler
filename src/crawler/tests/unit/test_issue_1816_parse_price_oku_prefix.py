"""Unit tests for Issue #1816: converter.parse_price with non-numeric prefix before 億."""

import pytest

from package.utils import converter


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("値下げ↓ 3億2,700万円", 327000000),
        ("新価格 1億500万円", 105000000),
        ("価格：2億万円", 200000000),
        ("1億2,000万円", 120000000),
        ("3億円", 300000000),
        ("億のみ", None),
        ("-", None),
        ("", None),
    ],
)
def test_parse_price_oku_with_prefix(raw: str, expected: int | None):
    assert converter.parse_price(raw) == expected
