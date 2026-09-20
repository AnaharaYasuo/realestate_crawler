# -*- coding: utf-8 -*-
"""UrlMatcher エラーログレベルの単体テスト (TDD)"""
from unittest.mock import MagicMock, patch
from package.utils.url_matcher import UrlMatcher


def test_url_matcher_query_error_logs_error():
    """UrlMatcher の DB クエリ例外時に DEBUG ではなく ERROR でログ出力されることを検証"""
    mock_qs = MagicMock()
    mock_qs.filter.side_effect = Exception("DB Connection Lost / Query Error")

    with patch("package.utils.url_matcher.logger.error") as mock_err:
        result = UrlMatcher.find_match_in_queryset(mock_qs, "pageUrl", "https://example.com/item/1")
        assert result is None
        mock_err.assert_called_once()
        log_msg = mock_err.call_args[0][0]
        assert "UrlMatcher query error" in log_msg
        assert "DB Connection Lost" in log_msg

