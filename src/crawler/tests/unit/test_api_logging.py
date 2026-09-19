# -*- coding: utf-8 -*-
from unittest.mock import patch
from package.utils.api_logger import mask_sensitive_data, get_logged_body_preview


def test_mask_sensitive_data():
    """機密情報キー（password, token, key, secret 等）が自動マスキングされることをテスト"""
    data = {
        "url": "https://example.com/property/1",
        "api_key": "secret-12345",
        "nested": {
            "token": "tok_abcdef",
            "normal_field": "ok_value"
        },
        "list_items": [
            {"password": "mypassword", "id": 1}
        ]
    }
    masked = mask_sensitive_data(data)
    assert masked["url"] == "https://example.com/property/1"
    assert masked["api_key"] == "***"
    assert masked["nested"]["token"] == "***"
    assert masked["nested"]["normal_field"] == "ok_value"
    assert masked["list_items"][0]["password"] == "***"
    assert masked["list_items"][0]["id"] == 1


def test_get_logged_body_preview_truncation():
    """2000文字を超える巨大ペイロードが適切に切り詰められることをテスト"""
    huge_text = "A" * 3000
    preview = get_logged_body_preview(huge_text, max_len=2000)
    assert len(preview) < 2100
    assert "... (truncated" in preview


def test_flask_app_request_response_logging():
    """Flask APIリクエストおよびレスポンスが正しくログ出力されることをテスト"""
    from main import app

    with app.test_client() as client, \
         patch("package.utils.api_logger.logging.info") as mock_info, \
         patch("package.utils.api_logger.logging.log") as mock_log:

        resp = client.post(
            "/api/evaluation/predict-by-url",
            json={"url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/123/"},
            headers={"Content-Type": "application/json"}
        )

        # [API Request] ログの検証
        req_calls = [str(c) for c in mock_info.call_args_list if "[API Request]" in str(c)]
        assert len(req_calls) >= 1
        assert "/api/evaluation/predict-by-url" in req_calls[0]
        assert "https://www.rehouse.co.jp/buy/mansion/bkdetail/123/" in req_calls[0]

        # [API Response] ログの検証
        resp_calls = [str(c) for c in mock_log.call_args_list if "[API Response]" in str(c)]
        assert len(resp_calls) >= 1
        assert "/api/evaluation/predict-by-url" in resp_calls[0]
        assert f"Status: {resp.status_code}" in resp_calls[0]
