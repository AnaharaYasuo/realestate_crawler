import unittest
from decimal import Decimal
from unittest.mock import MagicMock
from package.parser.baseParser import ParserBase
from package.utils.data_validator import PropertyDataValidator


class TestYieldAndValidatorThresholds(unittest.TestCase):
    def test_guard_gross_yield_auto_calculation(self):
        item = MagicMock()
        item.grossYield = None
        item.price = 200000000
        item.annualRent = 12000000
        item._meta.get_field.return_value.null = False

        ParserBase._guard_gross_yield(item)
        self.assertEqual(item.grossYield, Decimal("6.0"))

    def test_guard_gross_yield_monthly_rent_fallback(self):
        item = MagicMock()
        item.grossYield = Decimal("0.0")
        item.price = 50000000
        item.annualRent = None
        item.monthlyRent = 250000
        item._meta.get_field.return_value.null = False

        ParserBase._guard_gross_yield(item)
        self.assertEqual(item.grossYield, Decimal("6.0"))

    def test_guard_gross_yield_leaves_existing_positive_yield(self):
        item = MagicMock()
        item.grossYield = Decimal("7.5")
        item.price = 50000000
        item.annualRent = 1000000
        item._meta.get_field.return_value.null = False

        ParserBase._guard_gross_yield(item)
        self.assertEqual(item.grossYield, Decimal("7.5"))

    def test_validator_allows_toushi_portal_low_price(self):
        item = MagicMock()
        item.pageUrl = "https://toushi.homes.co.jp/bukkendetail/index/4641422/"
        item.price = 700000
        item.chimoku = "宅地"
        item.propertyName = "売地"
        item.address = "宮城県亘理郡亘理町"
        item.traffic = "JR常磐線 亘理駅"
        item.station1 = "亘理"
        item.biko = ""
        item.senyuMenseki = None
        item.tatemonoMenseki = None
        item.tochiMenseki = 150.0

        is_valid, reasons = PropertyDataValidator.validate_property(item, "tochi")
        self.assertTrue(is_valid, f"Expected valid, got: {reasons}")

    def test_validator_allows_high_price_up_to_50oku(self):
        item = MagicMock()
        item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F15BGA77/"
        item.propertyName = "三田ガーデンヒルズ"
        item.address = "東京都港区三田一丁目"
        item.traffic = "都営大江戸線 麻布十番駅"
        item.station1 = "麻布十番"
        item.price = 2380000000  # 23.8億円
        item.senyuMenseki = 250.0
        item.tatemonoMenseki = None
        item.tochiMenseki = None
        item.floorType_kai = 20
        item.madori = "3LDK"
        item.chikunengetsuStr = "2020年3月"

        is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
        self.assertTrue(is_valid, f"Expected valid, got: {reasons}")


if __name__ == "__main__":
    unittest.main()
