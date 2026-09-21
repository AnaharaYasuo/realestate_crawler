import os
import logging
from package.utils.logging_config import configure_logging

# Ensure logs directory exists within project directory
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
log_dir = os.path.join(_project_root, 'logs', 'crawler_logs')
if not os.path.isdir(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# 統合構造化ロガー初期化 (GCP Cloud Logging / JSON 形式対応)
configure_logging()
logger = logging.getLogger(__name__)
