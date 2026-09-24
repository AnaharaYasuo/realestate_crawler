# -*- coding: utf-8 -*-
"""
統合構造化ロギング設定モジュール (logging_config.py)

Google Cloud Logging (GCP Cloud Run / Cloud Functions / GKE) 準拠の構造化JSONログおよび
ローカル開発時のカラーコンソールログを透過的に提供します。
標準ライブラリの logging.getLogger(__name__) と structlog の双方を自動ブリッジします。
"""
import os
import sys
import logging
import datetime
from typing import Optional, Any
import structlog

GCP_SOURCE_LOCATION_KEY = "logging.googleapis.com/sourceLocation"
_configured = False


def _is_cloud_environment() -> bool:
    """GCP / クラウド実行環境かどうかを判定"""
    if os.getenv("IS_CLOUD", "").lower() in ("true", "1", "yes"):
        return True
    if any(os.getenv(k) for k in ("K_SERVICE", "CLOUD_RUN_JOB", "GOOGLE_CLOUD_PROJECT", "GAE_SERVICE")):
        return True
    return False


def add_gcp_cloud_logging_fields(logger, method_name, event_dict):
    """
    Google Cloud Logging がネイティブ認識するトップレベルフィールドを整形:
    - severity: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - message: ログサマリー文字列 (structlog の 'event' を message に昇格)
    - timestamp: ISO 8601 UTC形式
    - logging.googleapis.com/sourceLocation: {file, line, function}
    """
    # 1. severity マッピング
    raw_level = str(event_dict.pop("level", method_name or "info")).upper()
    severity_map = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARN": "WARNING",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
        "FATAL": "CRITICAL",
        "EXCEPTION": "ERROR",
    }
    event_dict["severity"] = severity_map.get(raw_level, raw_level)

    # 2. message フィールド
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")

    # 3. timestamp (未設定またはフォーマット調整)
    if "timestamp" not in event_dict:
        event_dict["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 4. sourceLocation (標準 logging Record または structlog callsite より抽出)
    record = event_dict.pop("_record", None)
    if record:
        event_dict[GCP_SOURCE_LOCATION_KEY] = {
            "file": getattr(record, "pathname", ""),
            "line": getattr(record, "lineno", 0),
            "function": getattr(record, "funcName", "")
        }
    elif "pathname" in event_dict or "lineno" in event_dict:
        f = event_dict.pop("pathname", "")
        l = event_dict.pop("lineno", 0)
        fn = event_dict.pop("func_name", "")
        event_dict[GCP_SOURCE_LOCATION_KEY] = {
            "file": f,
            "line": l,
            "function": fn
        }
    elif GCP_SOURCE_LOCATION_KEY not in event_dict:
        event_dict[GCP_SOURCE_LOCATION_KEY] = {
            "file": getattr(logger, "name", "root"),
            "line": 0,
            "function": ""
        }

    return event_dict


def configure_logging(
    force_reconfigure: bool = False,
    output_stream: Any = None,
    log_format: Optional[str] = None,
    log_level: Optional[str] = None
):
    """
    structlog および標準 logging を一括初期化。
    """
    global _configured
    if _configured and not force_reconfigure:
        return

    # 標準出力エンコーディングを UTF-8 に再構成（日本語文字化け防止）
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    stream = output_stream or sys.stdout

    # ログフォーマット決定: json または console
    if log_format is None:
        env_format = os.getenv("LOG_FORMAT", "").lower()
        if env_format in ("json", "console"):
            log_format = env_format
        elif _is_cloud_environment():
            log_format = "json"
        else:
            log_format = "console"

    # ログレベル決定
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, log_level, logging.INFO)

    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                add_gcp_cloud_logging_fields,
                structlog.processors.JSONRenderer(ensure_ascii=False)
            ]
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True)
            ]
        )

    # ルートロガーのハンドラ設定
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    # 既存ハンドラーをクリーンアップ
    root_logger.handlers.clear()

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    handler.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # structlog の構成
    structlog_processors = shared_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=structlog_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: Optional[str] = None):
    """構造化ロガーインスタンスを取得"""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


# モジュールインポート時にデフォルト設定
configure_logging()
logger = get_logger()
base_logger = logger
