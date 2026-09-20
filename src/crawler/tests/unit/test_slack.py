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


@pytest.mark.asyncio
async def test_is_alert_channel(monkeypatch):
    """is_alert_channel がアラートチャンネル名・ID・環境変数を正しく判定することをテスト"""
    from package.utils.slack import is_alert_channel
    
    assert is_alert_channel("alerts-mansion") is True
    assert is_alert_channel("alerts-kodate") is True
    assert is_alert_channel("alerts-tochi") is True
    assert is_alert_channel("alerts-invest-apartment") is True
    assert is_alert_channel("alerts-invest-kodate") is True
    assert is_alert_channel("property_alert") is True
    assert is_alert_channel("C0BJWUCTRNU") is True  # alerts-mansion ID
    assert is_alert_channel("c0bj6b4r3e0") is True  # alerts-invest-apartment (case-insensitive)
    
    # 非アラートチャンネル
    assert is_alert_channel("recommend-mansion") is False
    assert is_alert_channel("dev-channel") is False
    assert is_alert_channel("C0BJ87V7BM0") is False  # recommend-mansion ID
    assert is_alert_channel(None) is False
    assert is_alert_channel("") is False
    
    # 環境変数での動的設定
    monkeypatch.setenv("SLACK_ALERT_CUSTOM", "C_CUSTOM_ALERT")
    assert is_alert_channel("C_CUSTOM_ALERT") is True


@pytest.mark.asyncio
async def test_send_slack_message_alert_channel_logs_error(monkeypatch):
    """アラートチャンネル宛ての送信時に logger.error でメッセージ全文が出力されることをテスト"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "fake-channel")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ok": True})

    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post), \
         patch("package.utils.slack.logger.error") as mock_logger_error:
        alert_text = "🚨 【パースエラー】 10件の異常が発生しました"
        result = await send_slack_message(alert_text, channel="alerts-mansion")
        assert result is True
        
        # logger.error がアラートメッセージを含んで呼ばれたことを検証
        mock_logger_error.assert_called_once()
        logged_msg = mock_logger_error.call_args[0][0]
        assert "alerts-mansion" in logged_msg
        assert alert_text in logged_msg


@pytest.mark.asyncio
async def test_send_slack_message_non_alert_channel_no_error_log(monkeypatch):
    """通常チャンネル（recommend 等）宛て送信時は logger.error が呼ばれないことをテスト"""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ok": True})

    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post), \
         patch("package.utils.slack.logger.error") as mock_logger_error:
        normal_text = "✨ お宝物件を検出しました"
        result = await send_slack_message(normal_text, channel="recommend-mansion")
        assert result is True
        
        # logger.error は呼ばれないこと
        mock_logger_error.assert_not_called()


@pytest.mark.asyncio
async def test_send_crawling_summary_alert_logs_error(monkeypatch):
    """send_crawling_summary_alert 実行時にも logger.error でエラーログ出力されることをテスト"""
    from package.utils.slack import send_crawling_summary_alert
    
    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("SLACK_ALERT_PROPERTY_ALERT", "property_alert")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"ok": True})

    mock_post = MagicMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession.post", return_value=mock_post), \
         patch("package.utils.slack.logger.error") as mock_logger_error:
        summary_text = "📢 【クローリング実行状況レポート】 失敗: 1"
        result = await send_crawling_summary_alert(summary_text)
        assert result is True
        
        mock_logger_error.assert_called_once()
        logged_msg = mock_logger_error.call_args[0][0]
        assert "property_alert" in logged_msg
        assert summary_text in logged_msg


@pytest.mark.asyncio
async def test_send_dev_report_uses_slack_dev_channel(monkeypatch):
    """send_dev_report が SLACK_DEV_CHANNEL 環境変数で指定されたチャンネルへ投稿することをテスト"""
    from package.utils.slack import send_dev_report

    monkeypatch.setenv("SLACK_DEV_CHANNEL", "C0BKBHWD26T")

    with patch("package.utils.slack.send_slack_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        report_text = "📊 【日次価格推定精度診断】 (2026-09-20)"
        result = await send_dev_report(report_text)
        assert result is True

        mock_send.assert_called_once_with(report_text, "C0BKBHWD26T")


@pytest.mark.asyncio
async def test_send_dev_report_default_fallback(monkeypatch):
    """SLACK_DEV_CHANNEL 未設定時はデフォルトの 'dev-agent' チャンネルへ投稿されることをテスト"""
    from package.utils.slack import send_dev_report

    monkeypatch.delenv("SLACK_DEV_CHANNEL", raising=False)

    with patch("package.utils.slack.send_slack_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        report_text = "✅ 【リグレッションテスト完了報告】"
        result = await send_dev_report(report_text)
        assert result is True

        mock_send.assert_called_once_with(report_text, "dev-agent")



