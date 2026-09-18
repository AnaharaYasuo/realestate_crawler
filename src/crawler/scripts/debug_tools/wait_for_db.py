# -*- coding: utf-8 -*-
import os
import sys
import time
import logging

_cur = os.path.dirname(os.path.abspath(__file__))
_crawler_dir = os.path.dirname(os.path.dirname(_cur))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()
from django.db import connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def wait_for_db(max_retries: int = 40, retry_interval: float = 2.0) -> bool:
    logging.info(f"Waiting for database connection to be ready (up to {int(max_retries * retry_interval)}s)...")
    for i in range(1, max_retries + 1):
        try:
            connection.ensure_connection()
            logging.info("Database connection is ready and operational!")
            return True
        except Exception as e:
            logging.warning(f"Waiting for DB... ({i}/{max_retries}): {e}")
            time.sleep(retry_interval)
    logging.error("Database connection timed out!")
    return False

if __name__ == "__main__":
    success = wait_for_db()
    sys.exit(0 if success else 1)
