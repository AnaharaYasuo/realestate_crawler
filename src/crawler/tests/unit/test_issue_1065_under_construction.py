import unittest
from types import SimpleNamespace
from package.utils.data_validator import PropertyDataValidator, ERR_MISSING_AGE


class TestUnderConstructionAgeValidation(unittest.TestCase):
    def test_under_construction_kodate_allows_blank_age(self):
        item = SimpleNamespace(
            propertyName="テスト新築戸建",
            address="東京都世田谷区1-1-1",
            station1="世田谷",
            traffic="東急世田谷線 世田谷駅 徒歩5分",
            price=50000000,
            tatemonoMenseki=90.0,
            tochiMenseki=100.0,
            madori="3LDK",
            genkyo="建築中",
            currentStatus=None,
            chikunengetsu=None,
            chikunengetsuStr="",
        )
        is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
        self.assertNotIn(ERR_MISSING_AGE, reasons)
        self.assertTrue(is_valid, f"Expected valid, got reasons: {reasons}")

    def test_completed_kodate_requires_age(self):
        item = SimpleNamespace(
            propertyName="テスト中古戸建",
            address="東京都世田谷区1-1-1",
            station1="世田谷",
            traffic="東急世田谷線 世田谷駅 徒歩5分",
            price=50000000,
            tatemonoMenseki=90.0,
            tochiMenseki=100.0,
            madori="3LDK",
            genkyo="空家",
            currentStatus=None,
            chikunengetsu=None,
            chikunengetsuStr="",
        )
        is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
        self.assertIn(ERR_MISSING_AGE, reasons)
        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()
