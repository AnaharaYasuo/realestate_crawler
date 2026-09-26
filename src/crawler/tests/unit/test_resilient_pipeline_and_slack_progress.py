# -*- coding: utf-8 -*-
"""
Tests for resilient pipeline continuation on crawl failure and Slack progress reporting (Issue #492)
"""
import pytest
from unittest.mock import patch, MagicMock

from scripts.ops import run_pipeline
from scripts.ops.run_bulk_ml_evaluation import run_bulk_evaluation
from scripts.ops.send_recommendations import send_recommendations


def test_run_crawler_step_failure_continues():
    """クローリングステップ（Step 1/6）が失敗しても、Coordinator/通常実行では後続パイプラインを続行すること"""
    with patch("scripts.ops.run_pipeline.run_command", side_effect=RuntimeError("Crawl failed with exit code 1")), \
         patch("scripts.ops.run_pipeline.logger") as mock_logger:

        should_continue, crawler_ok = run_pipeline._run_crawler_step(
            is_task_array=False,
            is_coordinator=True,
            task_index=None,
            task_count=1,
            ops_dir="/tmp/ops",
            skip_portals=False,
        )

        assert should_continue is True
        assert crawler_ok is False
        assert any("Parallel Crawling encountered an error" in str(call) for call in mock_logger.error.call_args_list)


def test_run_crawler_step_timeout_reraised():
    """クローリングステップでTimeoutErrorが発生した場合は安全停止のために例外を再送出すること"""
    with patch("scripts.ops.run_pipeline.run_command", side_effect=TimeoutError("Deadline reached")):
        with pytest.raises(TimeoutError):
            run_pipeline._run_crawler_step(
                is_task_array=False,
                is_coordinator=True,
                task_index=None,
                task_count=1,
                ops_dir="/tmp/ops",
                skip_portals=False,
            )


def test_run_post_crawl_pipeline_isolates_step_failure():
    """後続パイプラインでML再学習等が失敗しても、バルク価格推定とお宝物件通知が実行されること"""
    executed_commands = []

    def mock_run_cmd(cmd, desc, timeout=None):
        executed_commands.append(desc)
        if "Step 3/6" in desc:
            raise RuntimeError("ML Re-training failed")
        return True

    with patch("scripts.ops.run_pipeline.run_command", side_effect=mock_run_cmd):
        failed_steps = run_pipeline._run_post_crawl_pipeline(
            crawler_dir="/tmp/crawler",
            ops_dir="/tmp/ops",
            maintenance_dir="/tmp/maintenance",
            debug_tools_dir="/tmp/debug",
            skip_portals=False,
        )

    # Step 3/6 が失敗リストに含まれること
    assert any("Step 3/6" in s for s in failed_steps)
    # Step 4（バルク価格予測）と Step 5（お宝物件通知）が実行リストに含まれていること
    assert any("Step 4/6" in cmd for cmd in executed_commands)
    assert any("Step 5/6" in cmd for cmd in executed_commands)


def test_run_post_crawl_pipeline_step4_failure_still_runs_step5():
    """Step 4（バルク評価）が失敗した場合でも、Step 5（お宝物件通知）がスキップされずに実行されること"""
    executed_commands = []

    def mock_run_cmd(cmd, desc, timeout=None):
        executed_commands.append(desc)
        if "Step 4/6" in desc:
            raise RuntimeError("Batch Estimation failed")
        return True

    with patch("scripts.ops.run_pipeline.run_command", side_effect=mock_run_cmd):
        failed_steps = run_pipeline._run_post_crawl_pipeline(
            crawler_dir="/tmp/crawler",
            ops_dir="/tmp/ops",
            maintenance_dir="/tmp/maintenance",
            debug_tools_dir="/tmp/debug",
            skip_portals=False,
        )

    assert any("Step 4/6" in s for s in failed_steps)
    assert any("Step 5/6" in cmd for cmd in executed_commands)


@pytest.mark.django_db
def test_run_bulk_ml_evaluation_slack_notifications():
    """run_bulk_evaluation が開始、モデル別進捗、完了時に Slack 進捗通知を送信することを検証"""
    sent_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        sent_messages.append(msg)
        return True

    fake_model = MagicMock()
    fake_model.__name__ = "MitsuiMansion"

    with patch("scripts.ops.run_bulk_ml_evaluation.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.run_bulk_ml_evaluation.get_all_property_models", return_value=[fake_model]), \
         patch("scripts.ops.run_bulk_ml_evaluation._evaluate_single_model", return_value=(10, 2)), \
         patch("scripts.ops.run_bulk_ml_evaluation.PropertyEvaluation.objects.all") as mock_all:
        mock_all.return_value.only.return_value = []

        run_bulk_evaluation(skip_portals=True)

    # 開始通知
    assert any("【バルク価格推定開始】" in m for m in sent_messages)
    # モデル単位の進捗通知（モデル名、評価件数、累計件数）
    assert any("【価格推定進捗】" in m and "MitsuiMansion" in m and "評価 10 件" in m and "累計 10 件完了" in m for m in sent_messages)
    # 完了通知
    assert any("【バルク価格推定完了】" in m and "評価完了: 10 件" in m for m in sent_messages)


@pytest.mark.django_db
def test_run_bulk_ml_evaluation_empty_models_fails():
    """モデルが0件の場合は開始通知を送らずエラー通知後に異常終了すること"""
    sent_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        sent_messages.append(msg)
        return True

    with patch("scripts.ops.run_bulk_ml_evaluation.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.run_bulk_ml_evaluation.get_all_property_models", return_value=[]), \
         patch("scripts.ops.run_bulk_ml_evaluation.PropertyEvaluation.objects.all") as mock_all:
        mock_all.return_value.only.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            run_bulk_evaluation(skip_portals=True)

        assert exc_info.value.code == 1

    assert any("【バルク価格推定エラー】" in m for m in sent_messages)
    assert not any("【バルク価格推定開始】" in m for m in sent_messages)


@pytest.mark.django_db
def test_send_recommendations_slack_notifications_with_candidates():
    """send_recommendations が候補ありの場合に開始・検出・配信完了サマリーを通知することを検証"""
    status_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        status_messages.append(msg)
        return True

    dummy_eval = MagicMock()
    dummy_eval.company = "mitsui"
    dummy_eval.property_type = "mansion"
    dummy_eval.property_url = "https://example.com/prop1"
    dummy_prop = MagicMock()

    with patch("scripts.ops.send_recommendations.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.send_recommendations._fetch_recommendation_candidates", return_value=[dummy_eval]), \
         patch("scripts.ops.send_recommendations.get_property_record", return_value=dummy_prop), \
         patch("scripts.ops.send_recommendations._evaluate_candidate", return_value=(True, "テスト割安", 90.0)), \
         patch("scripts.ops.send_recommendations._dispatch_single_recommendation", return_value=True):

        send_recommendations()

    # 開始通知
    assert any("【お宝物件スクリーニング開始】" in m for m in status_messages)
    # 候補検出通知
    assert any("【お宝物件検出】 1 件の候補物件を検出しました" in m for m in status_messages)
    # 配信完了通知
    assert any("【お宝物件配信完了】 計 1/1 件" in m for m in status_messages)


@pytest.mark.django_db
def test_send_recommendations_slack_notifications_no_candidates():
    """send_recommendations が候補0件の場合に正常な0件案内を通知することを検証"""
    status_messages = []

    async def fake_send_crawling_summary_alert(msg: str):
        status_messages.append(msg)
        return True

    with patch("scripts.ops.send_recommendations.send_crawling_summary_alert", side_effect=fake_send_crawling_summary_alert), \
         patch("scripts.ops.send_recommendations._fetch_recommendation_candidates", return_value=[]):

        send_recommendations()

    assert any("【お宝物件スクリーニング開始】" in m for m in status_messages)
    assert any("【お宝物件通知】 現在配信基準を満たす新規お宝物件はありませんでした (0件)。" in m for m in status_messages)
