# -*- coding: utf-8 -*-
"""Unit tests for check_sonar_remote.py (Issue #299)."""
import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from scripts.debug_tools.check_sonar_remote import (
    DEFAULT_TIMEOUT_SEC,
    SonarApiException,
    SonarTimeoutException,
    fetch_quality_gate,
    fetch_unresolved_issues,
    main,
)


def test_default_timeout_is_finite():
    """デフォルトタイムアウトが10秒以下の有限値であること"""
    assert isinstance(DEFAULT_TIMEOUT_SEC, (int, float))
    assert 0 < DEFAULT_TIMEOUT_SEC <= 10.0


def test_fetch_quality_gate_success():
    """正常系: Quality Gate APIレスポンスが正しくパースされること"""
    mock_response_data = {
        "projectStatus": {
            "status": "OK",
            "conditions": [
                {"metricKey": "new_reliability_rating", "status": "OK", "actualValue": "1"}
            ],
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result = fetch_quality_gate(pr_number=287, timeout=5.0)
        assert result["status"] == "OK"
        assert len(result["conditions"]) == 1
        mock_urlopen.assert_called_once()
        _, kwargs = mock_urlopen.call_args
        assert kwargs.get("timeout") == 5.0


def test_fetch_quality_gate_timeout():
    """タイムアウト時: SonarTimeoutExceptionが送出されること"""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        with pytest.raises(SonarTimeoutException) as exc_info:
            fetch_quality_gate(pr_number=287, timeout=2.0)
        assert "timed out after 2.0s" in str(exc_info.value)


def test_fetch_quality_gate_http_error():
    """HTTPエラー時: SonarApiExceptionが送出されること"""
    http_err = urllib.error.HTTPError(
        url="https://sonarcloud.io/api/qualitygates/project_status",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(SonarApiException) as exc_info:
            fetch_quality_gate(pr_number=99999, timeout=5.0)
        assert "HTTP 404" in str(exc_info.value)


def test_fetch_unresolved_issues_success():
    """正常系: 未解決課題APIレスポンスが正しくパースされること"""
    mock_issues_data = {
        "total": 1,
        "issues": [
            {
                "rule": "python:S3776",
                "component": "src/crawler/test.py",
                "line": 42,
                "message": "Refactor function",
                "severity": "CRITICAL",
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_issues_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        issues, total = fetch_unresolved_issues(pr_number=287, timeout=5.0)
        assert total == 1
        assert len(issues) == 1
        assert issues[0]["rule"] == "python:S3776"


def test_main_cli_timeout_handling(capsys):
    """CLI実行時: タイムアウト発生時に終了コード2で終了しハングしないこと"""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        code = main(["--pr", "287", "--timeout", "1.5"])
        assert code == 2
        captured = capsys.readouterr()
        assert "TIMEOUT" in captured.err or "timed out" in captured.err


def test_positive_finite_timeout_validation():
    """不正なタイムアウト（0, 負数, nan, inf, 文字列）はArgumentTypeErrorで拒否されること"""
    for invalid_val in ["0", "-1", "nan", "inf", "-inf", "abc"]:
        with pytest.raises(SystemExit):
            main(["--pr", "287", "--timeout", invalid_val])
