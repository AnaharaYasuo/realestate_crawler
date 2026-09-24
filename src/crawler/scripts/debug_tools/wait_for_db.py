import logging
import os
import socket
import sys
import time

_cur = os.path.dirname(os.path.abspath(__file__))
_crawler_dir = os.path.dirname(os.path.dirname(_cur))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings

realestateSettings.configure()
from django.db import connection

logger = logging.getLogger(__name__)


def wait_for_db(max_retries: int = 40, retry_interval: float = 2.0, socket_timeout: float = 3.0) -> bool:
    """DB 疎通待機。ソケットによる事前疎通確認を行い、未起動時の長時間ハング (TCP SYN timeout) を防止する。"""
    settings_dict = getattr(connection, "settings_dict", {})
    host = settings_dict.get("HOST") or os.getenv("DB_HOST", "127.0.0.1")
    port = int(settings_dict.get("PORT") or os.getenv("DB_PORT", "3306"))

    logger.info(f"Waiting for database connection to be ready ({host}:{port}, up to {int(max_retries * retry_interval)}s)...")
    for i in range(1, max_retries + 1):
        try:
            # 1. ソケットによる迅速な疎通チェック (最大 socket_timeout 秒で fail-fast)
            with socket.create_connection((host, port), timeout=socket_timeout):
                pass

            # 2. Django connection による認証・DB 稼働確認
            connection.ensure_connection()
            logger.info("Database connection is ready and operational!")
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Waiting for DB... ({i}/{max_retries}): {e}")
            time.sleep(retry_interval)
    logger.error("Database connection timed out!")
    return False



if __name__ == "__main__":
    success = wait_for_db()
    sys.exit(0 if success else 1)

