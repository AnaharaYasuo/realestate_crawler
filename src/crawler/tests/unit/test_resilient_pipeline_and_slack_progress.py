# -*- coding: utf-8 -*-
"""
Tests for resilient pipeline continuation on crawl failure and Slack progress reporting (Issue #492)
"""
import pytest
from unittest.mock import patch

from scripts.ops import run_pipeline
from scripts.ops.run_bulk_ml_evaluation import run_bulk_evaluation
from scripts.ops.send_recommendations import send_recommendations


def test_run_crawler_step_failure_continues():
    """クローリングステップ（Step 1/6）が失敗しても、Coordinator/通常実行では後続パイプラインを続行すること"""
    with patch("scripts.ops.run_pipeline.run_command", side_effect=RuntimeError("Crawl failed with exit code 1")), \
         patch("scripts.ops.run_pipeline.logger") as mock_logger:

        should_continue = run_pipeline._run_crawler_step(
            is_task_array=False,
            is_coordinator=True,
            task_index=None,
            task_count=1,
            ops_dir="/tmp/ops",
            skip_portals=False,
        )

        assert should_continue is True
        # エラーがログに記録されていること
        assert any("クローリング" in str(call) or "Crawling" in str(call) or "failed" in str(call).lower() for call in mock_logger.error.call_args_list)


def test_run_post_crawl_pipeline_isolates_step_failure():
    """後続パイプラインでML再学習等が失敗しても、バルク価格推定とお宝物件通知が実行されること"""
    executed_commands = []

    def mock_run_cmd(cmd, desc, timeout=None, ignore_errors=False):
        executed_commands.append(desc)
        if "Step 3/6" in desc:
            if not ignore_errors:
                raise RuntimeError("ML Re-training failed")
            return False
        return True

    with patch("scripts.ops.run_pipeline.run_command", side_effect=mock_run_cmd):
        run_pipeline._run_post_crawl_pipeline(
            crawler_dir="/tmp/crawler",
            ops_dir="/tmp/ops",
            maintenance_dir="/tmp/maintenance",
            debug_tools_dir="/tmp/debug",
            skip_portals=False,
        )

    # Step 4（バルク価格予測）と Step 5（お宝物件通知）が実行リストに含まれていること
    assert any("Step 4/6" in cmd for cmd in executed_commands)
    assert any("Step 5/6" in cmd for cmd in executed_commands)


@pytest.mark.django_db
def test_run_bulk_ml_evaluation_slack_notifications():
    """run_bulk_evaluation が開始および完了時に Slack 進捗通知を送信することを検証"""
    sent_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        sent_messages.append(msg)
        return True

    with patch("scripts.ops.run_bulk_ml_evaluation.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.run_bulk_ml_evaluation.get_all_property_models", return_value=[]), \
         patch("scripts.ops.run_bulk_ml_evaluation.PropertyEvaluation.objects.all") as mock_all:
        mock_all.return_value.only.return_value = []

        run_bulk_evaluation(skip_portals=True)

    # 開始通知と完了通知が送信されたこと
    assert any("【バルク価格推定開始】" in m for m in sent_messages)
    assert any("【バルク価格推定完了】" in m for m in sent_messages)


@pytest.mark.django_db
def test_send_recommendations_slack_notifications():
    """send_recommendations が開始および完了サマリーを Slack に通知することを検証"""
    status_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        status_messages.append(msg)
        return True

    with patch("scripts.ops.send_recommendations.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.send_recommendations._fetch_recommendation_candidates", return_value=[]):

        send_recommendations()

    # 開始通知および完了（0件案内含む）通知が送信されたこと
    assert any("【お宝物件スクリーニング開始】" in m for m in status_messages)
    assert any("【お宝物件通知】" in m or "【お宝物件配信完了】" in m for m in status_messages)
