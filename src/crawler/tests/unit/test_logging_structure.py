# -*- coding: utf-8 -*-
import io
import json
import logging
import os
import sys
import pytest

from package.utils.logging_config import configure_logging, get_logger


def test_logging_gcp_structured_format(monkeypatch):
    """GCP / JSON モードにおいて、Google Cloud Logging 準拠のフィールドが出力されることを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="DEBUG")

    logger = get_logger("test.structured")
    logger.info("テストメッセージ: 三井のリハウス マンション", company="mitsui", count=10)

    output = stream.getvalue().strip()
    assert output, "Log output should not be empty"

    data = json.loads(output)
    # Cloud Logging required / recognized keys
    assert data.get("severity") == "INFO"
    assert "テストメッセージ: 三井のリハウス マンション" in data.get("message", "")
    assert "timestamp" in data
    assert data.get("company") == "mitsui"
    assert data.get("count") == 10
    assert "logging.googleapis.com/sourceLocation" in data


def test_standard_logging_bridge(monkeypatch):
    """標準 logging.getLogger(__name__) からの呼び出しも自動的に構造化 JSON に変換されることを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="INFO")

    std_logger = logging.getLogger("standard.test")
    std_logger.warning("標準ロガーからの警告テスト")

    output = stream.getvalue().strip()
    data = json.loads(output)
    assert data.get("severity") == "WARNING"
    assert "標準ロガーからの警告テスト" in data.get("message", "")


def test_exception_structured_traceback(monkeypatch):
    """例外発生時にスタックトレースが単一のJSONログ内に内包されることを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="INFO")

    logger = get_logger("test.exception")
    try:
        raise ValueError("意図的なテスト例外エラー")
    except Exception as ex:
        logger.error("処理中にエラーが発生しました", exc_info=ex)

    output = stream.getvalue().strip()
    data = json.loads(output)
    assert data.get("severity") == "ERROR"
    assert "処理中にエラーが発生しました" in data.get("message", "")
    assert "exception" in data or "stack_trace" in data or "ValueError" in data.get("message", "")


def test_log_level_filtering(monkeypatch):
    """LOG_LEVEL=INFO の場合、DEBUG ログが出力されないことを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="INFO")

    logger = get_logger("test.level")
    logger.debug("このデバッグメッセージは出力されないはずです")
    logger.info("このインフォメッセージは出力されるはずです")

    lines = [l for l in stream.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data.get("severity") == "INFO"
    assert "このインフォメッセージ" in data.get("message", "")
