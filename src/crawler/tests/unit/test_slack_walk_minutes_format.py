"""Slack 通知文の徒歩分「分」付与テスト"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from types import SimpleNamespace

from scripts.ops.send_recommendations import _format_single_access, _format_walk_text


def test_format_walk_text_appends_fun():
    assert _format_walk_text("10") == "徒歩10分"
    assert _format_walk_text("10分") == "徒歩10分"
    assert _format_walk_text("徒歩8分") == "徒歩8分"


def test_format_single_access_uses_numeric_fallback_with_fun():
    prop = SimpleNamespace(railway1="京王線", station1="明大前", railwayWalkMinute1Str="8", busUse1=0)
    assert _format_single_access(prop, 1) == "京王線 明大前 徒歩8分"
    prop = SimpleNamespace(railway1="東武東上線", station1="上福岡", railwayWalkMinute1Str="", railwayWalkMinute1=12, busUse1=0)
    assert _format_single_access(prop, 1) == "東武東上線 上福岡 徒歩12分"
