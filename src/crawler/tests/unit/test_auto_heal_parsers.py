# -*- coding: utf-8 -*-
from unittest.mock import patch
from scripts.debug_tools.auto_heal_parsers import notify_auto_heal_request


def test_notify_auto_heal_request_with_targets():
    heal_targets = [
        {
            "company": "mitsui",
            "property_type": "mansion",
            "reason": "価格異常極小: 50万円",
            "url": "https://example.com/prop/1",
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
        assert "mitsui (mansion)" in call_args
        assert "**検知件数**: 1 件" in call_args


def test_notify_auto_heal_request_more_than_five_targets():
    heal_targets = [
        {
            "company": f"company_{i}",
            "property_type": "kodate",
            "reason": f"error_{i}",
            "url": f"https://example.com/prop/{i}",
        }
        for i in range(6)
    ]
    with patch("scripts.debug_tools.auto_heal_parsers.send_dev_report") as mock_send:

        async def fake_coro(*args, **kwargs):
            return True

        mock_send.side_effect = fake_coro

        notify_auto_heal_request(heal_targets)
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert "**検知件数**: 6 件" in call_args
        assert "他 1 件" in call_args


def test_notify_auto_heal_request_exception_swallowed():
    heal_targets = [
        {
            "company": "test",
            "property_type": "tochi",
            "reason": "error",
            "url": "https://example.com/prop",
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
