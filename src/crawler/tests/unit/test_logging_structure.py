import io
import json
import logging

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

    lines = [line for line in stream.getvalue().strip().split("\n") if line.strip()]
    data = next((json.loads(l) for l in lines if "標準ロガーからの警告テスト" in json.loads(l).get("message", "")), None)
    assert data is not None
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

    lines = [line for line in stream.getvalue().strip().split("\n") if line.strip()]
    data = next((json.loads(l) for l in lines if "処理中にエラーが発生しました" in json.loads(l).get("message", "")), None)
    assert data is not None
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


def test_trace_and_debug_levels(monkeypatch):
    """新設 TRACE レベル (5) および DEBUG レベル (10) の連携とフィルタリングを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "TRACE")
    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="TRACE")

    logger = get_logger("test.trace")
    logger.trace("構造化トレースログテスト", step="xpath_eval")
    logging.trace("標準ロガートレーステスト")
    logger.debug("構造化デバッグログテスト")

    lines = [l for l in stream.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 3
    parsed = [json.loads(l) for l in lines]

    assert parsed[0].get("severity") == "DEBUG"
    assert parsed[0].get("original_level") == "TRACE"
    assert "構造化トレースログテスト" in parsed[0].get("message", "")
    assert parsed[0].get("step") == "xpath_eval"

    assert parsed[1].get("severity") == "DEBUG"
    assert parsed[1].get("original_level") == "TRACE"
    assert "標準ロガートレーステスト" in parsed[1].get("message", "")

    assert parsed[2].get("severity") == "DEBUG"
    assert "構造化デバッグログテスト" in parsed[2].get("message", "")

    # LOG_LEVEL=DEBUG の場合、TRACE はフィルタリングされる
    stream_debug = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream_debug, log_format="json", log_level="DEBUG")
    logger.trace("このトレースメッセージは出力されない")
    logger.debug("このデバッグメッセージは出力される")

    debug_lines = [l for l in stream_debug.getvalue().strip().split("\n") if l.strip()]
    assert len(debug_lines) == 1
    debug_parsed = json.loads(debug_lines[0])
    assert debug_parsed.get("severity") == "DEBUG"
    assert "このデバッグメッセージは出力される" in debug_parsed.get("message", "")


def test_no_raw_print_in_production_code():
    """本番コード（main.py および package/）内に生の print() 呼び出しが残存していないことを静的検査"""
    import subprocess
    from pathlib import Path
    # 当前ファイルから crawler ルート (src/crawler) を基準に解決
    crawler_root = Path(__file__).resolve().parent.parent.parent
    cmd = [
        "git", "grep", "-n", "-P", r"\bprint\s*\(", "--",
        "main.py",
        "package"
    ]
    res = subprocess.run(cmd, cwd=str(crawler_root), capture_output=True, text=True, check=False)
    # print() が一切存在しなければ git grep の終了コードは 1 となる
    matching_lines = [
        line for line in res.stdout.splitlines()
        if not line.strip().startswith("#") and line.strip()
    ]
    assert len(matching_lines) == 0, "Raw print() found in production code:\n" + "\n".join(matching_lines)


def test_no_newline_in_message_payload(monkeypatch):
    """改行を含むHTMLやテキストがログに出力されても複数行に分割されず、単一JSONログとして出力されることを検証"""
    monkeypatch.setenv("LOG_FORMAT", "json")
    stream = io.StringIO()
    configure_logging(force_reconfigure=True, output_stream=stream, log_format="json", log_level="INFO")

    from package.api.middleware import LoggingMiddleware
    from package.utils.api_logger import get_logged_body_preview

    raw_html = "<html>\n<head>\n<title>404</title>\n</head>\n<body>\n<h1>Error</h1>\n</body></html>\n"
    sanitized_mw = LoggingMiddleware._sanitize_log_body(raw_html)
    sanitized_preview = get_logged_body_preview(raw_html)

    assert "\n" not in sanitized_mw
    assert "\r" not in sanitized_mw
    assert "</body></html>" in sanitized_mw

    assert "\n" not in sanitized_preview
    assert "\r" not in sanitized_preview
    assert "</body></html>" in sanitized_preview

    logger = get_logger("test.sanitization")
    logger.warning("Sanitized Middleware Response", body=sanitized_mw)

    lines = [line for line in stream.getvalue().strip().split("\n") if line.strip()]
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data.get("severity") == "WARNING"
    assert data.get("body") == sanitized_mw

    # Truncation and length capping test
    preview_capped = get_logged_body_preview("y" * 1000, max_len=80)
    assert len(preview_capped) <= 80
    assert "... (truncated, total 1000 chars)" in preview_capped

    # Additional coverage for get_logged_body_preview branches
    assert get_logged_body_preview(None) is None
    assert get_logged_body_preview({"user": "john", "password": "secret", "nested": ["data"]}) is not None
    assert get_logged_body_preview({"long_key": "val " * 500}, max_len=50) is not None
    assert get_logged_body_preview(b"binary data \n here") == "binary data here"
    assert get_logged_body_preview(b"b" * 1000, max_len=60) is not None
    assert get_logged_body_preview(12345) == "12345"

    # Coverage for package.api import
    import package.api
    assert package.api.logger is not None
