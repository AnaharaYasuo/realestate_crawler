# -*- coding: utf-8 -*-
from unittest.mock import patch
import pytest
from scripts.debug_tools.auto_heal_parsers import (
    aggregate_and_sort_targets,
    notify_auto_heal_request,
)


@pytest.fixture(autouse=True)
def reset_gemini_circuit_breaker():
    import os
    import scripts.debug_tools.auto_heal_parsers as ahp

    path = ahp._get_cb_state_path()
    if os.path.exists(path):
        os.remove(path)
    yield
    if os.path.exists(path):
        os.remove(path)


def test_aggregate_and_sort_targets_counts_frequency_and_sorts():
    raw_targets = [
        {"company": "mitsui", "property_type": "mansion", "reason": "価格異常極小: 50万円", "url": "https://example.com/1"},
        {"company": "sumifu", "property_type": "kodate", "reason": "間口パース漏れ警告 (接道: '間口5m')", "url": "https://example.com/2"},
        {"company": "mitsui", "property_type": "mansion", "reason": "価格異常極小: 30万円", "url": "https://example.com/3"},
        {"company": "mitsui", "property_type": "mansion", "reason": "価格異常極小: 80万円", "url": "https://example.com/4"},
        {"company": "tokyu", "property_type": "tochi", "reason": "土地面積異常極小: 2㎡", "url": "https://example.com/5"},
        {"company": "tokyu", "property_type": "tochi", "reason": "土地面積異常極小: 1㎡", "url": "https://example.com/6"},
    ]
    # mitsui mansion: 3件, tokyu tochi: 2件, sumifu kodate: 1件
    # 各グループから代表1件ずつ抽出されるため合計3件
    aggregated = aggregate_and_sort_targets(raw_targets, max_targets=10)
    assert len(aggregated) == 3
    # 頻度順に並んでいるか（1位グループ: mitsui mansion, 2位グループ: tokyu tochi, 3位グループ: sumifu kodate）
    assert aggregated[0]["company"] == "mitsui"
    assert aggregated[0]["frequency"] == 3
    assert aggregated[1]["company"] == "tokyu"
    assert aggregated[1]["frequency"] == 2
    assert aggregated[2]["company"] == "sumifu"
    assert aggregated[2]["frequency"] == 1


def test_aggregate_and_sort_targets_truncates_at_max_targets():
    # 15種類の異なるエラー
    raw_targets = [
        {"company": f"c_{i}", "property_type": "mansion", "reason": f"error_{i}", "url": f"https://example.com/{i}"}
        for i in range(15)
    ]
    aggregated = aggregate_and_sort_targets(raw_targets, max_targets=10)
    assert len(aggregated) == 10


def test_notify_auto_heal_request_with_targets():
    heal_targets = [
        {
            "company": "mitsui",
            "property_type": "mansion",
            "reason": "価格異常極小: 50万円",
            "url": "https://example.com/prop/1",
            "frequency": 3,
        }
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:

        async def fake_coro(*args, **kwargs):
            return True

        mock_send.side_effect = fake_coro

        notify_auto_heal_request(heal_targets)
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert "[AUTO_HEAL_REQ]" in call_args
        assert "/auto-heal" in call_args
        assert "mitsui (mansion) [3件]" in call_args
        assert "**検知件数**: 1 件" in call_args


def test_notify_auto_heal_request_more_than_five_targets():
    heal_targets = [
        {
            "company": f"company_{i}",
            "property_type": "kodate",
            "reason": f"error_{i}",
            "url": f"https://example.com/prop/{i}",
            "frequency": 1,
        }
        for i in range(8)
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:

        async def fake_coro(*args, **kwargs):
            return True

        mock_send.side_effect = fake_coro

        notify_auto_heal_request(heal_targets)
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert "**検知件数**: 8 件" in call_args
        assert "他 3 件" in call_args


def test_notify_auto_heal_request_exception_swallowed():
    heal_targets = [
        {
            "company": "test",
            "property_type": "tochi",
            "reason": "error",
            "url": "https://example.com/prop",
            "frequency": 1,
        }
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:

        async def fail_coro(*args, **kwargs):
            raise RuntimeError("Slack API error")

        mock_send.side_effect = fail_coro

        # 例外が外へ漏れずに正常終了することを検証
        notify_auto_heal_request(heal_targets)
        assert mock_send.call_count == 1


def test_notify_auto_heal_request_empty_targets():
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:
        notify_auto_heal_request([])
        assert not mock_send.called


def test_notify_auto_heal_request_with_ai_summary():
    heal_targets = [
        {
            "company": "mitsui",
            "property_type": "mansion",
            "reason": "価格異常極小: 50万円",
            "url": "https://example.com/prop/1",
            "frequency": 3,
        }
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:

        async def fake_coro(*args, **kwargs):
            return True

        mock_send.side_effect = fake_coro

        ai_summary = "• mitsui mansion 3件: 価格50万。セレクター修正要"
        notify_auto_heal_request(heal_targets, ai_summary=ai_summary)
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert ai_summary in call_args
        assert "[AUTO_HEAL_REQ]" in call_args


def test_summarize_errors_with_gemini_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from scripts.debug_tools.auto_heal_parsers import summarize_errors_with_gemini

    targets = [
        {"company": "tokyu", "property_type": "tochi", "reason": "土地面積極小", "url": "https://example.com", "frequency": 2}
    ]
    summary = summarize_errors_with_gemini(targets)
    assert "tokyu (tochi) [2件]: 土地面積極小" in summary


def test_summarize_errors_with_gemini_calls_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-mock")
    from scripts.debug_tools.auto_heal_parsers import summarize_errors_with_gemini

    class MockResp:
        text = "• tokyu tochi 2件: 土地面積セレクター不整合"

    class MockModels:
        def generate_content(self, model, contents):
            return MockResp()

    class MockClient:
        def __init__(self, *args, **kwargs):
            self.models = MockModels()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("scripts.debug_tools.auto_heal_parsers.genai") as mock_genai:
        mock_genai.Client = MockClient
        targets = [
            {"company": "tokyu", "property_type": "tochi", "reason": "土地面積極小", "url": "https://example.com", "frequency": 2}
        ]
        res = summarize_errors_with_gemini(targets)
        assert "tokyu tochi 2件: 土地面積セレクター不整合" in res


def test_summarize_errors_with_gemini_circuit_breaker_on_consecutive_timeouts(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-mock")
    import scripts.debug_tools.auto_heal_parsers as ahp

    # リセット
    ahp._consecutive_gemini_timeouts = 0
    ahp._gemini_cooldown_until = None

    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        @property
        def models(self):
            class M:
                def generate_content(self, *a, **k):
                    raise RuntimeError("Gemini API call timed out after 10000ms")
            return M()

    with patch("scripts.debug_tools.auto_heal_parsers.genai") as mock_genai:
        mock_genai.Client = TimeoutClient
        targets = [{"company": "tokyu", "property_type": "tochi", "reason": "土地面積極小", "url": "https://example.com", "frequency": 2}]

        # 1回目のタイムアウト
        res1 = ahp.summarize_errors_with_gemini(targets)
        count1, cd1 = ahp._load_cb_state()
        assert count1 == 1
        assert cd1 is None
        assert "tokyu (tochi) [2件]: 土地面積極小" in res1

        # 2回目のタイムアウト -> サーキットブレイカー発動
        res2 = ahp.summarize_errors_with_gemini(targets)
        count2, cd2 = ahp._load_cb_state()
        assert count2 == 2
        assert cd2 is not None
        assert "tokyu (tochi) [2件]: 土地面積極小" in res2

        # クールダウン中は即時デフォルトサマリー返却
        res3 = ahp.summarize_errors_with_gemini(targets)
        assert "tokyu (tochi) [2件]: 土地面積極小" in res3
