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


@pytest.mark.asyncio
async def test_verify_url_active_empty():
    """空のURLが指定された場合、Falseを返すことをテスト"""
    from package.utils.slack import verify_url_active
    result = await verify_url_active("")
    assert result is False


@pytest.mark.asyncio
async def test_verify_url_active_success():
    """URL接続が成功(200 OK)した場合、Trueを返すことをテスト"""
    from package.utils.slack import verify_url_active
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="<html><title>Active Property</title><body>Normal Page</body></html>")
    
    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock()
    
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        result = await verify_url_active("http://example.com")
        assert result is True


@pytest.mark.asyncio
async def test_verify_url_active_failed():
    """URL接続が失敗(404等)した場合、Falseを返すことをテスト"""
    from package.utils.slack import verify_url_active
    
    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.text = AsyncMock(return_value="<html><title>Not Found</title></html>")
    
    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = MagicMock()
    
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        result = await verify_url_active("http://example.com")
        assert result is False


@pytest.mark.asyncio
async def test_verify_url_active_exception():
    """URLリクエストで例外が発生した場合、Falseを返すことをテスト"""
    from package.utils.slack import verify_url_active
    
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Connection refused")):
        result = await verify_url_active("http://example.com")
        assert result is False


@pytest.mark.asyncio
async def test_verify_url_active_inactive_content():
    """HTML内に掲載終了のフレーズ、もしくはタイトルに掲載終了が含まれる場合、Falseを返すことをテスト"""
    from package.utils.slack import verify_url_active
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="<html><title>エラー</title><body>お探しの物件は、掲載が終了したか、成約済みになった可能性があります。</body></html>")
    
    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = MagicMock()
    
    with patch("aiohttp.ClientSession.get", return_value=mock_get):
        result = await verify_url_active("http://example.com")
        assert result is False


