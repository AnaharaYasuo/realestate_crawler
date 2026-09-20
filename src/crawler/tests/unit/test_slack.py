# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

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


@pytest.mark.asyncio
async def test_send_dev_report_empty_env_fallback(monkeypatch):
    """SLACK_DEV_CHANNELが空文字の場合でも 'dev-agent' にフォールバックすることをテスト"""
    from package.utils.slack import send_dev_report

    monkeypatch.setenv("SLACK_DEV_CHANNEL", "")

    with patch("package.utils.slack.send_slack_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        report_text = "✅ 【空文字フォールバックテスト】"
        result = await send_dev_report(report_text)
        assert result is True

        mock_send.assert_called_once_with(report_text, "dev-agent")


@pytest.mark.asyncio
async def test_send_dev_report_explicit_channel_override(monkeypatch):
    """channel 引数が明示された場合は環境変数より優先されることをテスト"""
    from package.utils.slack import send_dev_report

    monkeypatch.setenv("SLACK_DEV_CHANNEL", "C0BKBHWD26T")

    with patch("package.utils.slack.send_slack_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        report_text = "✅ 【明示指定テスト】"
        result = await send_dev_report(report_text, channel="custom-channel")
        assert result is True

        mock_send.assert_called_once_with(report_text, "custom-channel")


@pytest.mark.asyncio
async def test_resolve_channel_id_already_id():
    """C/G/Dで始まる有効なChannel IDはそのまま返却されることをテスト"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_session = MagicMock()
    channel_id = "C0BJWUCTRNU"
    result = await resolve_channel_id(mock_session, channel_id, "fake-token")
    assert result == channel_id
    mock_session.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_channel_id_lookup_success():
    """チャンネル名が指定された場合に conversations.list から ID を解決することをテスト"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value={
        "ok": True,
        "channels": [
            {"id": "C0111111111", "name": "general"},
            {"id": "C0999999999", "name": "dev-agent"},
        ]
    })
    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get)

    result = await resolve_channel_id(mock_session, "#dev-agent", "fake-token")
    assert result == "C0999999999"


@pytest.mark.asyncio
async def test_resolve_channel_id_lookup_fallback():
    """解決失敗時は元のチャンネル名がフォールバック返却されることをテスト"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value={"ok": False, "error": "channel_not_found"})
    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get.__aexit__ = AsyncMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get)

    result = await resolve_channel_id(mock_session, "unknown-channel", "fake-token")
    assert result == "unknown-channel"


@pytest.mark.asyncio
async def test_resolve_channel_id_pagination_success():
    """複数ページにまたがる conversations.list から2ページ目でIDを解決できることをテスト"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    resp_page1 = AsyncMock()
    resp_page1.json = AsyncMock(return_value={
        "ok": True,
        "channels": [{"id": "C0111111111", "name": "general"}],
        "response_metadata": {"next_cursor": "cursor_page_2"}
    })
    get_page1 = MagicMock()
    get_page1.__aenter__ = AsyncMock(return_value=resp_page1)
    get_page1.__aexit__ = AsyncMock()

    resp_page2 = AsyncMock()
    resp_page2.json = AsyncMock(return_value={
        "ok": True,
        "channels": [{"id": "C0222222222", "name": "dev-agent"}],
        "response_metadata": {"next_cursor": ""}
    })
    get_page2 = MagicMock()
    get_page2.__aenter__ = AsyncMock(return_value=resp_page2)
    get_page2.__aexit__ = AsyncMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=[get_page1, get_page2])

    result = await resolve_channel_id(mock_session, "dev-agent", "fake-token")
    assert result == "C0222222222"
    assert mock_session.get.call_count == 2

    first_request = mock_session.get.call_args_list[0]
    assert first_request.kwargs["headers"] == {"Authorization": "Bearer fake-token"}
    assert first_request.kwargs["params"] == {
        "types": "public_channel,private_channel",
        "limit": "200",
    }
    assert mock_session.get.call_args_list[1].kwargs["params"]["cursor"] == "cursor_page_2"


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_channel", [None, ""])
async def test_resolve_channel_id_empty_value_skips_api_call(empty_channel):
    """空のチャンネル値はAPI呼び出しをせず、そのまま返すことをテスト。"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_session = MagicMock()

    assert await resolve_channel_id(mock_session, empty_channel, "fake-token") == empty_channel
    mock_session.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_channel_id_normalizes_hash_and_case():
    """チャンネル名は先頭の#と大文字小文字を無視して照合することをテスト。"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(
        return_value={
            "ok": True,
            "channels": [{"id": "C0999999999", "name": "Dev-Agent"}],
            "response_metadata": {"next_cursor": ""},
        }
    )
    response_context = MagicMock()
    response_context.__aenter__ = AsyncMock(return_value=mock_resp)
    response_context.__aexit__ = AsyncMock()
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=response_context)

    assert await resolve_channel_id(mock_session, "#DEV-AGENT", "fake-token") == "C0999999999"


@pytest.mark.asyncio
async def test_resolve_channel_id_request_exception_falls_back_to_original_name():
    """Slack APIへの接続例外時にも呼び出し元のチャンネル指定を保持することをテスト。"""
    from scripts.debug_tools.check_latest_slack import resolve_channel_id

    mock_session = MagicMock()
    mock_session.get.side_effect = aiohttp.ClientError("connection failed")

    assert await resolve_channel_id(mock_session, "dev-agent", "fake-token") == "dev-agent"


@pytest.mark.asyncio
async def test_check_latest_slack_verify_without_token_does_not_open_session(monkeypatch, capsys):
    """トークン欠損時は明示的に終了し、Slackへ接続しないことをテスト。"""
    from scripts.debug_tools import check_latest_slack

    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    with patch.object(check_latest_slack.aiohttp, "ClientSession") as mock_client_session:
        await check_latest_slack.verify("dev-agent")

    mock_client_session.assert_not_called()
    assert capsys.readouterr().out == "SLACK_BOT_TOKEN not set.\n"


@pytest.mark.asyncio
async def test_check_latest_slack_verify_resolves_channel_and_prints_messages(monkeypatch, capsys):
    """指定名をIDに解決し、そのIDで履歴を取得して内容を表示することをテスト。"""
    from scripts.debug_tools import check_latest_slack

    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    history_response = AsyncMock()
    history_response.json = AsyncMock(
        return_value={"ok": True, "messages": [{"ts": "123.456", "text": "latest report"}]}
    )
    history_context = MagicMock()
    history_context.__aenter__ = AsyncMock(return_value=history_response)
    history_context.__aexit__ = AsyncMock()
    session = MagicMock()
    session.get = MagicMock(return_value=history_context)
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock()

    with patch.object(check_latest_slack.aiohttp, "ClientSession", return_value=session_context), patch.object(
        check_latest_slack,
        "resolve_channel_id",
        new=AsyncMock(return_value="C0999999999"),
    ) as mock_resolve:
        await check_latest_slack.verify("#dev-agent")

    mock_resolve.assert_awaited_once_with(session, "#dev-agent", "fake-token")
    session.get.assert_called_once_with(
        "https://slack.com/api/conversations.history?channel=C0999999999&limit=2",
        headers={"Authorization": "Bearer fake-token"},
    )
    output = capsys.readouterr().out
    assert "TS: 123.456" in output
    assert "latest report" in output


@pytest.mark.asyncio
async def test_check_latest_slack_verify_defaults_to_dev_agent(monkeypatch):
    """チャンネル設定がすべて欠損した場合はdev-agentを解決対象にすることをテスト。"""
    from scripts.debug_tools import check_latest_slack

    monkeypatch.setenv("SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.delenv("SLACK_DEV_CHANNEL", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)
    history_response = AsyncMock()
    history_response.json = AsyncMock(return_value={"ok": False, "error": "channel_not_found"})
    history_context = MagicMock()
    history_context.__aenter__ = AsyncMock(return_value=history_response)
    history_context.__aexit__ = AsyncMock()
    session = MagicMock()
    session.get = MagicMock(return_value=history_context)
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock()

    with patch.object(check_latest_slack.aiohttp, "ClientSession", return_value=session_context), patch.object(
        check_latest_slack,
        "resolve_channel_id",
        new=AsyncMock(return_value="dev-agent"),
    ) as mock_resolve:
        await check_latest_slack.verify()

    mock_resolve.assert_awaited_once_with(session, "dev-agent", "fake-token")
