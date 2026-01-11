import structlog
import logging
import sys

def configure_logging():
    """structlog を使用した構造化ログの設定を行います。"""
    
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # 開発環境（コンテナ外など）ではコンソールで見やすく、
    # 運用環境（Docker内など）では JSON 形式で出力するように切り替え可能
    # ここでは一貫して JSON 形式をデフォルトとします
    processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 標準の logging モジュールも structlog 経由で出力するように設定
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

logger = structlog.get_logger()
base_logger = logger # Alias for easier migration
