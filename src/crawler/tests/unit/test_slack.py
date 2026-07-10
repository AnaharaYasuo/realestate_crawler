# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from package.utils.slack import send_slack_message

@pytest.mark.asyncio
async def test_send_slack_message_missing_env(monkeypatch):
    """環境変数が設定されていない場合、送信をスキップしてFalseを返すことをテスト"""
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)
    
    result = await send_slack_message("Test message")
    assert result is False

@pytest.mark.asyncio
async def test_send_slack_message_success(monkeypatch):
    """Slack APIが正常(ok=True)を返した場合、Trueを返すことをテスト"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "fake-channel")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ok": True})

    # aiohttp.ClientSession.post をコンテキストマネージャのモックとして定義
    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post):
        result = await send_slack_message("Hello Test")
        assert result is True

@pytest.mark.asyncio
async def test_send_slack_message_api_error(monkeypatch):
    """Slack APIがエラー(ok=False)を返した場合、Falseを返すことをテスト"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "fake-channel")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ok": False, "error": "invalid_auth"})

    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post):
        result = await send_slack_message("Hello Test")
        assert result is False

@pytest.mark.asyncio
async def test_send_slack_message_http_error(monkeypatch):
    """HTTPステータスが200以外の場合、Falseを返すことをテスト"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "fake-channel")

    mock_resp = AsyncMock()
    mock_resp.status = 500

    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post):
        result = await send_slack_message("Hello Test")
        assert result is False
