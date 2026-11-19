# -*- coding: utf-8 -*-
from unittest.mock import patch
import pytest
from scripts.debug_tools.auto_heal_parsers import (
    aggregate_and_sort_targets,
    notify_auto_heal_request,
)


@pytest.fixture(autouse=True)
def reset_gemini_circuit_breaker(tmp_path, monkeypatch):
    import scripts.debug_tools.auto_heal_parsers as ahp

    fake_cb_path = str(tmp_path / "gemini_circuit_breaker.json")
    monkeypatch.setattr(ahp, "_get_cb_state_path", lambda: fake_cb_path)
    ahp._save_cb_state(0, None)
    yield
    ahp._save_cb_state(0, None)


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
    aggregated = aggregate_and_sort_targets(raw_targets)
    assert len(aggregated) == 3
    # 頻度順に並んでいるか（1位グループ: mitsui mansion, 2位グループ: tokyu tochi, 3位グループ: sumifu kodate）
    assert aggregated[0]["company"] == "mitsui"
    assert aggregated[0]["frequency"] == 3
    assert aggregated[1]["company"] == "tokyu"
    assert aggregated[1]["frequency"] == 2
    assert aggregated[2]["company"] == "sumifu"
    assert aggregated[2]["frequency"] == 1


def test_aggregate_and_sort_targets_truncates_at_max_targets():
    # 60種類の異なるエラーでデフォルト50件への切り捨てを検証
    raw_targets = [
        {"company": f"c_{i}", "property_type": "mansion", "reason": f"error_{i}", "url": f"https://example.com/{i}"}
        for i in range(60)
    ]
    aggregated = aggregate_and_sort_targets(raw_targets)
    assert len(aggregated) == 50

    # 明示的な max_targets 指定時
    aggregated_custom = aggregate_and_sort_targets(raw_targets, max_targets=20)
    assert len(aggregated_custom) == 20


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
        notify_auto_heal_request(heal_targets, ai_summary=ai_summary, total_detected=25)
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert ai_summary in call_args
        assert "[AUTO_HEAL_REQ]" in call_args
        assert "**検知件数**: 25 件 (優先グループ 1 件)" in call_args


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

        # 2回目のタイムアウト -> サーキットブレイカー発動 (クールダウン設定・カウントは0リセット)
        res2 = ahp.summarize_errors_with_gemini(targets)
        count2, cd2 = ahp._load_cb_state()
        assert count2 == 0
        assert cd2 is not None
        assert "tokyu (tochi) [2件]: 土地面積極小" in res2

        # クールダウン中は即時デフォルトサマリー返却
        res3 = ahp.summarize_errors_with_gemini(targets)
        assert "tokyu (tochi) [2件]: 土地面積極小" in res3


def test_parse_slack_message_to_targets_data_monitor_alert():
    from scripts.debug_tools.auto_heal_parsers import parse_slack_message_to_targets

    text = """
:warning: 【不動産クローラー データ監視アラート - MANSION】

:rotating_light: **検出された異常/エラー: 25181 件**
  - :x: [Critical] [mitsui/mansion] 価格異常 (0.0万円), 面積異常 (0.0㎡) | パークシティ中野 ザ タワー エアーズ | URL: <https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/>
  - :bulb: [Warning] [sumifu/tochi] 面積異常 (0.0㎡) | 土地物件 | URL: https://www.stepon.co.jp/tochi/detail_12345/
"""
    targets = parse_slack_message_to_targets(text, channel_name="alerts-mansion", ts="1234567890.123")
    assert len(targets) == 2

    t0 = targets[0]
    assert t0["company"] == "mitsui"
    assert t0["property_type"] == "mansion"
    assert "価格異常 (0.0万円), 面積異常 (0.0㎡)" in t0["reason"]
    assert "(#alerts-mansion)" in t0["reason"]
    assert t0["propertyName"] == "パークシティ中野 ザ タワー エアーズ"
    assert t0["url"] == "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/"
    assert t0["source"] == "slack"

    t1 = targets[1]
    assert t1["company"] == "sumifu"
    assert t1["property_type"] == "tochi"
    assert "面積異常 (0.0㎡)" in t1["reason"]
    assert t1["propertyName"] == "土地物件"
    assert t1["url"] == "https://www.stepon.co.jp/tochi/detail_12345/"


def test_summarize_errors_with_gemini_includes_failed_pipeline_steps(monkeypatch):
    """パイプライン失敗ステップ (Step 3 ML, Step 4 Bulk Eval等) がサマリーに含まれることを検証 (Issue #1391)"""
    from scripts.debug_tools.auto_heal_parsers import summarize_errors_with_gemini

    monkeypatch.setenv("TESTING", "1")
    failed_steps = ["Step 3/6: ML Model Re-Training", "Step 4/6: Batch Estimation & Investment Evaluation"]
    targets = [{"company": "athome", "property_type": "mansion", "reason": "価格異常", "url": "https://example.com"}]

    summary = summarize_errors_with_gemini(targets, failed_pipeline_steps=failed_steps)
    assert "【パイプライン重大失敗ステップ】" in summary
    assert "Step 3/6: ML Model Re-Training" in summary
    assert "Step 4/6: Batch Estimation & Investment Evaluation" in summary
    assert "athome (mansion)" in summary


def test_scan_logs_for_tracebacks_extracts_and_groups(tmp_path):
    """ログファイル内の Traceback を検出し、サイト推定・グルーピングできることを検証"""
    from scripts.debug_tools.auto_heal_parsers import scan_logs_for_tracebacks

    log_file = tmp_path / "crawler_run.log"
    log_content = (
        "2026-11-20 07:00:00 INFO Starting crawler\n"
        "Traceback (most recent call last):\n"
        '  File "/app/src/crawler/package/parser/nomuraParser.py", line 123, in parse_mansion\n'
        "    val = soup.select_one('.price').text\n"
        "AttributeError: 'NoneType' object has no attribute 'text'\n"
        "2026-11-20 07:01:00 INFO Next item\n"
        "Traceback (most recent call last):\n"
        '  File "/app/src/crawler/package/parser/nomuraParser.py", line 123, in parse_mansion\n'
        "    val = soup.select_one('.price').text\n"
        "AttributeError: 'NoneType' object has no attribute 'text'\n"
        "Traceback (most recent call last):\n"
        '  File "/app/src/crawler/package/parser/homesParser.py", line 45, in parse_kodate\n'
        "    int('abc')\n"
        "ValueError: invalid literal for int() with base 10: 'abc'\n"
    )
    log_file.write_text(log_content, encoding="utf-8")

    targets = scan_logs_for_tracebacks(log_dirs=[str(tmp_path)], max_age_hours=24)
    assert len(targets) == 2

    nomura_t = next(t for t in targets if t["company"] == "nomura")
    assert nomura_t["property_type"] == "mansion"
    assert nomura_t["count"] == 2
    assert "AttributeError" in nomura_t["reason"]
    assert "nomuraParser.py:123" in nomura_t["location"]
    assert nomura_t["source"] == "log_traceback"

    homes_t = next(t for t in targets if t["company"] == "homes")
    assert homes_t["property_type"] == "kodate"
    assert homes_t["count"] == 1
    assert "ValueError" in homes_t["reason"]


def test_parse_slack_message_to_targets_traceback_alert():
    """[AUTO_HEAL_TRACEBACK] Slackアラートが修正対象としてパースされることを検証"""
    from scripts.debug_tools.auto_heal_parsers import parse_slack_message_to_targets

    text = (
        ":rotating_light: [AUTO_HEAL_TRACEBACK] ログからスタックトレースを検知しました\n"
        "- サイト: nomura | 種別: mansion | 例外: AttributeError: 'NoneType' object has no attribute 'text' "
        "| 箇所: nomuraParser.py:123 | 件数: 2件"
    )
    targets = parse_slack_message_to_targets(text, channel_name="dev-agent", ts="1700000000.000")
    assert len(targets) == 1
    t = targets[0]
    assert t["company"] == "nomura"
    assert t["property_type"] == "mansion"
    assert "AttributeError" in t["reason"]
    assert t["source"] == "slack"


def test_notify_traceback_alerts_sends_slack(monkeypatch):
    """notify_traceback_alerts が send_dev_report 経由で Slack 通知を送ることを検証"""
    from scripts.debug_tools import auto_heal_parsers as ahp

    sent_messages = []
    monkeypatch.setattr(ahp, "send_dev_report", lambda msg: sent_messages.append(msg) or True)

    targets = [
        {
            "company": "nomura",
            "property_type": "mansion",
            "reason": "スタックトレース検知: AttributeError: 'NoneType' object has no attribute 'text'",
            "location": "nomuraParser.py:123",
            "count": 2,
            "url": "https://www.nomura.co.jp/",
            "source": "log_traceback",
        }
    ]
    res = ahp.notify_traceback_alerts(targets)
    assert res is True
    assert len(sent_messages) == 1
    assert "[AUTO_HEAL_TRACEBACK]" in sent_messages[0]
    assert "サイト: nomura" in sent_messages[0]
    assert "nomuraParser.py:123" in sent_messages[0]



