import unittest
from types import SimpleNamespace
from package.utils.data_validator import PropertyDataValidator, ERR_MISSING_FLOOR
from scripts.debug_tools.auto_heal_parsers import parse_slack_message_to_targets


class TestAutoHealBulkFixes(unittest.TestCase):
    def test_parse_slack_message_ignores_business_warnings(self):
        # Business warnings like 再建築不可 or 間口0m should not be treated as parser errors
        text1 = "- :x: [Warning] [mitsui/kodate] 再建築不可警告 (無道路地ペナルティ対象) | 北沢4丁目 戸建 | URL: <https://www.rehouse.co.jp/buy/kodate/bkdetail/F10BGA1C/>"
        text2 = "- :x: [Warning] [mitsui/kodate] 間口0m警告 (無道路地ペナルティ対象) | 目黒区目黒本町5丁目 | URL: <https://www.rehouse.co.jp/buy/kodate/bkdetail/F7FAPA0B/>"
        text3 = "- :x: [Critical] [mitsui/mansion] 価格異常 (0.0万円), 面積異常 (0.0㎡) | パークシティ中野 | URL: <https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/>"

        t1 = parse_slack_message_to_targets(text1, channel_name="alerts-kodate")
        self.assertEqual(len(t1), 0, "Business warning 再建築不可 should be ignored")

        t2 = parse_slack_message_to_targets(text2, channel_name="alerts-kodate")
        self.assertEqual(len(t2), 0, "Business warning 間口0m should be ignored")

        t3 = parse_slack_message_to_targets(text3, channel_name="alerts-mansion")
        self.assertEqual(len(t3), 1, "Real critical parse error should be ingested")

    def test_invest_apartment_allows_low_price_and_small_area(self):
        # Low price invest property
        item = SimpleNamespace(
            propertyName="テスト投資用アパート",
            address="東京都世田谷区1-1-1",
            station1="世田谷",
            traffic="東急世田谷線 世田谷駅 徒歩5分",
            price=850000, # 85万円
            senyuMenseki=14.0, # 14㎡
            grossYield=18.5,
            pageUrl="https://toushi.homes.co.jp/bukkendetail/index/4617572/",
            biko="利回り18.5%",
            chimoku="宅地",
        )
        is_valid, reasons = PropertyDataValidator.validate_property(item, "investment_apartment")
        self.assertTrue(is_valid, f"Expected valid for invest unit apartment, got: {reasons}")


if __name__ == "__main__":
    unittest.main()
