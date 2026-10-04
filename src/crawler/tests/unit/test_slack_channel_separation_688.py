# -*- coding: utf-8 -*-
"""Issue #688: Slack通知チャンネル責務分離のユニットテスト

受入基準:
1. run_ml_pipeline.py の send_aggregated_crawl_report が #property_alert ではなく #dev-agent へ送信されること
2. 失敗タスクが含まれる場合のみ #property_alert にも警告が発報されること
3. run_all_crawlers.py の完了サマリーで、全成功時は #dev-agent、失敗あり時は #property_alert へ送信されること
4. send_recommendations.py の種別不明時フォールバック先が dev-agent であること
5. slack.py の get_alert_channel の未知種別フォールバック先が dev-agent であること
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime

from package.utils.slack import get_alert_channel
from scripts.ops import run_ml_pipeline
from scripts.ops.send_recommendations import _get_target_slack_channel


def test_get_alert_channel_fallback_is_dev_agent(monkeypatch):
    """未知の物件種別の場合、property_alert ではなく SLACK_DEV_CHANNEL / dev-agent にフォールバックすること"""
    monkeypatch.delenv("SLACK_DEV_CHANNEL", raising=False)
    monkeypatch.delenv("SLACK_ALERT_PROPERTY_ALERT", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)

    # 未知の種別
    ch = get_alert_channel("unknown_type")
    assert ch == "dev-agent"

    # SLACK_DEV_CHANNEL が設定されている場合
    monkeypatch.setenv("SLACK_DEV_CHANNEL", "C_DEV_AGENT_ID")
    ch_env = get_alert_channel("unknown_type")
    assert ch_env == "C_DEV_AGENT_ID"


def test_send_recommendations_fallback_is_dev_agent(monkeypatch):
    """お宝物件推薦で種別不明物件の場合、property_alert ではなく SLACK_DEV_CHANNEL / dev-agent にフォールバックすること"""
    monkeypatch.delenv("SLACK_RECOMMEND_CHANNEL_ID", raising=False)
    monkeypatch.delenv("SLACK_DEV_CHANNEL", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)

    eval_rec = MagicMock()
    eval_rec.property_type = "unknown_type"
    prop = MagicMock()

    ch = _get_target_slack_channel(eval_rec, prop, "テスト物件")
    assert ch == "dev-agent"

    monkeypatch.setenv("SLACK_DEV_CHANNEL", "C_DEV_AGENT_ID")
    ch_env = _get_target_slack_channel(eval_rec, prop, "テスト物件")
    assert ch_env == "C_DEV_AGENT_ID"


def test_ml_pipeline_aggregated_report_sends_to_dev_report_on_success(monkeypatch):
    """全ジョブ成功時、クローラー集約レポートは send_dev_report のみ呼び出され、send_crawling_summary_alert は呼ばれないこと"""
    rows = [
        MagicMock(task_index=0, results_json=[{"company": "mitsui", "property_type": "mansion", "status": "success"}]),
    ]
    latest = MagicMock(return_value=rows)
    mock_dev_report = AsyncMock(return_value=True)
    mock_summary_alert = AsyncMock(return_value=True)

    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", latest)
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", mock_dev_report)
    monkeypatch.setattr(run_ml_pipeline, "send_crawling_summary_alert", mock_summary_alert)

    target_date = datetime.date(2026, 10, 5)
    result = run_ml_pipeline.send_aggregated_crawl_report(target_date)

    assert result is True
    mock_dev_report.assert_awaited_once()
    mock_summary_alert.assert_not_called()


def test_ml_pipeline_aggregated_report_alerts_property_alert_on_failure(monkeypatch):
    """失敗ジョブを含む場合、クローラー集約レポートは send_dev_report に加え send_crawling_summary_alert にも発報されること"""
    rows = [
        MagicMock(task_index=0, results_json=[{"company": "tokyu", "property_type": "tochi", "status": "failed", "exit_code": 1}]),
    ]
    latest = MagicMock(return_value=rows)
    mock_dev_report = AsyncMock(return_value=True)
    mock_summary_alert = AsyncMock(return_value=True)

    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", latest)
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", mock_dev_report)
    monkeypatch.setattr(run_ml_pipeline, "send_crawling_summary_alert", mock_summary_alert)

    target_date = datetime.date(2026, 10, 5)
    result = run_ml_pipeline.send_aggregated_crawl_report(target_date)

    assert result is True
    mock_dev_report.assert_awaited_once()
    mock_summary_alert.assert_awaited_once()
