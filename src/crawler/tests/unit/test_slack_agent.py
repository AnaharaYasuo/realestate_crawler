# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from package.utils.slack_agent import SlackAgent


def test_is_user_allowed():
    agent = SlackAgent(allowed_users=["U12345", "U67890"])
    assert agent.is_user_allowed("U12345") is True
    assert agent.is_user_allowed("U99999") is False


def test_is_user_allowed_empty_allowed():
    # 安全仕様: allowed_users が未設定または空の場合は全拒絶 (Deny All)
    agent = SlackAgent(allowed_users=[])
    assert agent.is_user_allowed("ANY_USER") is False


@pytest.mark.asyncio
async def test_run_streaming_agent_mock():
    agent = SlackAgent(allowed_users=["U12345"], conversation_id="test-session-123")
    mock_client = MagicMock()
    mock_client.chat_update = MagicMock()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout.readline = AsyncMock(
            side_effect=[b"Processing instruction...\n", b"Done.\n", b""]
        )
        mock_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_proc

        await agent.run_streaming_agent(
            mock_client, "C123", "123.456", "pytest実行して"
        )
        assert mock_client.chat_update.called


def test_should_process_slack_event_auto_heal_from_bot():
    from package.utils.slack_agent import should_process_slack_event

    event = {
        "bot_id": "B_CRAWLER_BOT",
        "text": "🚨 **[AUTO_HEAL_REQ] クローラー自己修復リクエスト**\n5件の異常を検知。\n/auto-heal",
    }
    # 許可Botリスト未指定時（フェイルクローズにより不許可）
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_bot"

    # 許可Botリストに含まれる場合
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}, allowed_bots={"B_CRAWLER_BOT"}
    )
    assert allowed is True
    assert instruction == "/auto-heal"
    assert reason == "auto_heal_authorized"

    # 許可Botリストに含まれない不正なBotの場合
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}, allowed_bots={"B_OTHER_BOT"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_bot"


def test_should_process_slack_event_auto_heal_from_user():
    from package.utils.slack_agent import should_process_slack_event

    # 許可ユーザーからの [AUTO_HEAL_REQ]
    event = {
        "user": "U12345",
        "text": "🚨 [AUTO_HEAL_REQ] 障害復旧\n/auto-heal",
    }
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is True
    assert instruction == "/auto-heal"
    assert reason == "auto_heal_authorized"

    # 未許可ユーザーからの [AUTO_HEAL_REQ]
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U_OTHER"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_user"

    # 許可リスト空の場合
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users=set()
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_user"

    # 送信者情報なしの場合
    event_no_sender = {
        "text": "🚨 [AUTO_HEAL_REQ] 送信元不明\n/auto-heal",
    }
    allowed, instruction, reason = should_process_slack_event(
        event_no_sender, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_sender"


def test_should_process_slack_event_normal_bot_rejected():
    from package.utils.slack_agent import should_process_slack_event

    event = {"bot_id": "B_SOME_BOT", "text": "定期クロールを開始します。"}
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "bot_rejected"


def test_should_process_slack_event_self_agent_loop_prevention():
    from package.utils.slack_agent import should_process_slack_event

    # エージェント自身の返信に [AUTO_HEAL_REQ] の文字が引用されていたとしても無限ループ防止で破棄
    event = {
        "bot_id": "B_AGENT_BOT",
        "text": "✅ **Antigravity Agent 実行完了**\n\n```\n[AUTO_HEAL_REQ] 修復完了\n```",
    }
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "self_agent"


def test_should_process_slack_event_allowed_user():
    from package.utils.slack_agent import should_process_slack_event

    event = {"user": "U12345", "text": "最新のコミット状況を教えて"}
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is True
    assert instruction == "最新のコミット状況を教えて"
    assert reason == "user_authorized"


def test_should_process_slack_event_unauthorized_user():
    from package.utils.slack_agent import should_process_slack_event

    event = {"user": "U_UNKNOWN", "text": "システムを再起動して"}
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "unauthorized_user"


def test_should_process_slack_event_empty_text():
    from package.utils.slack_agent import should_process_slack_event

    event = {"user": "U12345", "text": "   "}
    allowed, instruction, reason = should_process_slack_event(
        event, allowed_users={"U12345"}
    )
    assert allowed is False
    assert instruction == ""
    assert reason == "empty_text"


def test_is_self_agent_message():
    from package.utils.slack_agent import is_self_agent_message

    assert is_self_agent_message("🚀 Antigravity Agent 本体を起動中...") is True
    assert is_self_agent_message("✅ Antigravity Agent 実行完了") is True
    assert is_self_agent_message("通常のユーザーメッセージ") is False


def test_truncate_text():
    from package.utils.slack_agent import _truncate_text

    short_text = "abc" * 10
    assert _truncate_text(short_text) == short_text

    long_text = "x" * 4000
    truncated = _truncate_text(long_text, max_len=100)
    assert truncated.startswith("... [前部省略] ...\n")
    assert len(truncated) <= 4000


def test_build_agy_cmd_with_and_without_conversation():
    from package.utils.slack_agent import _build_agy_cmd

    cmd_with_conv = _build_agy_cmd("conv-123", "pytest実行")
    assert "--conversation" in cmd_with_conv
    assert "conv-123" in cmd_with_conv
    assert "pytest実行" in cmd_with_conv
    assert "--dangerously-skip-permissions" in cmd_with_conv

    cmd_without_conv = _build_agy_cmd(None, "pytest実行")
    assert "--continue" in cmd_without_conv
    assert "pytest実行" in cmd_without_conv


def test_find_agy_bin():
    from package.utils.slack_agent import _find_agy_bin

    with patch("shutil.which", return_value="/usr/local/bin/agy"):
        assert _find_agy_bin() == "/usr/local/bin/agy"
