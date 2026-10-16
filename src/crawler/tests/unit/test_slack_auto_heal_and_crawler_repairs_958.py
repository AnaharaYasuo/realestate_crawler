# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, patch
import pytest

from scripts.debug_tools.auto_heal_parsers import (
    aggregate_and_sort_targets,
    parse_slack_message_to_targets,
    fetch_slack_error_targets,
)
from package.parser.homesParser import HomesMansionParser
from package.parser.athomeParser import AthomeMansionParser
from package.utils import converter


def test_parse_slack_message_zero_count_alert():
    msg = """⚠️ 【クローリング警告: 0件取得検知】
• 対象サイト: athome (アットホーム)
• 種別: mansion (マンション)
• 取得件数: 0 件
• 理由: クローラーが正常終了しましたが、新規・更新物件が0件でした。"""
    targets = parse_slack_message_to_targets(msg, channel_name="alerts-mansion", ts="1740000000.0")
    assert len(targets) == 1
    t = targets[0]
    assert t["company"] == "athome"
    assert t["property_type"] == "mansion"
    assert "0件取得検知" in t["reason"]
    assert t["source"] == "slack"


def test_parse_slack_message_parser_exception():
    msg = """❌ 【パース例外 / データ異常検知】
• サイト: homes
• 種別: mansion
• URL: https://www.homes.co.jp/mansion/b-12345/
• エラー: AttributeError: 'NoneType' object has no attribute 'group' / priceStr parse failure"""
    targets = parse_slack_message_to_targets(msg, channel_name="dev-agent", ts="1740000001.0")
    assert len(targets) == 1
    t = targets[0]
    assert t["company"] == "homes"
    assert t["property_type"] == "mansion"
    assert t["url"] == "https://www.homes.co.jp/mansion/b-12345/"
    assert "AttributeError" in t["reason"]
    assert t["source"] == "slack"


def test_parse_slack_message_low_count_summary():
    msg = """:bar_chart: *クローリング・価格推定バッチ実行結果サマリー*
• athome: 0件
• homes: 2件
• mitsui: 210件"""
    targets = parse_slack_message_to_targets(msg, channel_name="property_alert", ts="1740000002.0")
    assert len(targets) >= 2
    companies = [t["company"] for t in targets]
    assert "athome" in companies
    assert "homes" in companies


@pytest.mark.asyncio
async def test_fetch_slack_error_targets_integration():
    fake_messages = [
        {"text": "⚠️ 【クローリング警告: 0件取得検知】\n• 対象サイト: athome\n• 種別: kodate\n• 取得件数: 0 件", "ts": "1"},
        {"text": "❌ 【パース例外】\n• サイト: homes\n• 種別: tochi\n• URL: https://www.homes.co.jp/tochi/1/\n• エラー: KeyError", "ts": "2"},
        {"text": "クローリング完了: 正常終了", "ts": "3"},
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.fetch_all_slack_channel_messages", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("alerts-kodate", m) for m in fake_messages]
        targets = await fetch_slack_error_targets(limit=10)
        assert len(targets) == 2
        assert targets[0]["company"] in ["athome", "homes"]
        assert targets[1]["company"] in ["athome", "homes"]


def test_homes_mansion_parser_price_resilience():
    parser = HomesMansionParser()
    assert parser.property_type == "mansion"
    assert converter.parse_price("価格未定") is None
    assert converter.parse_price("") is None
    assert converter.parse_price("相談") is None
    assert converter.parse_price("5,480万円") == 54800000
    assert converter.parse_price("1億2,000万円") == 120000000


def test_athome_mansion_parser_resilience():
    parser = AthomeMansionParser()
    assert parser.property_type == "mansion"
    assert converter.parse_price("4,980万円") == 49800000
    assert converter.parse_price("未定") is None

    # Test aggregate_and_sort_targets with slack targets
    targets = [{"company": "athome", "property_type": "mansion", "reason": "0件取得"}]
    sorted_targets = aggregate_and_sort_targets(targets)
    assert len(sorted_targets) == 1
    assert sorted_targets[0]["company"] == "athome"
