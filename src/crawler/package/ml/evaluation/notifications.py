"""
Slack 進捗および完了サマリー通知モジュール (Issue #716)
"""

import logging

from asgiref.sync import async_to_sync
from package.utils.slack import send_dev_report

logger = logging.getLogger(__name__)


def notify_slack(msg: str) -> None:
    """Slack dev-agent チャンネルへ進捗・完了通知を送信"""
    try:
        report_func = globals().get("send_dev_report", send_dev_report)
        async_to_sync(report_func)(msg)
    except (RuntimeError, OSError, ConnectionError) as se:
        logger.warning("Failed to send Slack report: %s", se)

