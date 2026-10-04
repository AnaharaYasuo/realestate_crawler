from package.utils.batch_metrics import (
    BatchMetrics,
    format_batch_duration,
    format_throughput,
)


def test_format_batch_duration():
    assert format_batch_duration(0) == "0秒"
    assert format_batch_duration(45) == "45秒"
    assert format_batch_duration(65) == "1分5秒"
    assert format_batch_duration(3665) == "1時間1分5秒"
    assert format_batch_duration(7200) == "2時間0分0秒"


def test_format_throughput():
    # 100 items in 10 seconds -> 10.0 items/sec, 100.0 ms/item
    tp, lat = format_throughput(100, 10.0)
    assert tp == 10.0
    assert lat == 100.0

    # 0 items -> 0.0 items/sec, 0.0 ms/item
    tp, lat = format_throughput(0, 10.0)
    assert tp == 0.0
    assert lat == 0.0

    # 0 seconds -> 0.0 items/sec, 0.0 ms/item (zero division guard)
    tp, lat = format_throughput(100, 0.0)
    assert tp == 0.0
    assert lat == 0.0


def test_batch_metrics_basic_lifecycle():
    metrics = BatchMetrics(job_name="Test Job", total_count=100)
    assert metrics.job_name == "Test Job"
    assert metrics.total_count == 100
    assert metrics.processed_count == 0
    assert metrics.skipped_count == 0
    assert metrics.failed_count == 0

    metrics.record_processed(10)
    metrics.record_skipped(5)
    metrics.record_failed(1)

    assert metrics.processed_count == 10
    assert metrics.skipped_count == 5
    assert metrics.failed_count == 1
    assert metrics.remaining_count == 84

    # Finish and verify duration
    elapsed = metrics.finish()
    assert elapsed >= 0.0
    assert metrics.end_time is not None


def test_batch_metrics_slack_summary():
    metrics = BatchMetrics(job_name="Bulk ML Evaluation", total_count=1000)
    metrics.start_time = 1700000000.0
    metrics.record_processed(200)
    metrics.record_skipped(800)
    metrics.set_metric("passed_count", 45)
    metrics.set_metric("duplicate_count", 10)
    metrics.set_metric("concurrency", 4)
    metrics.finish(fixed_end_time=1700000020.0)  # 20 seconds

    summary = metrics.build_slack_summary(
        title="バルク価格推定完了",
        custom_lines=[
            "• スクリーニング: 1次通過(割安候補) 45 件 | 重複除外 10 件",
            "• 並行スレッド: 4",
        ]
    )

    assert "【バルク価格推定完了】" in summary
    assert "所要: 20秒" in summary
    assert "対象総数 1,000 件" in summary
    assert "評価完了: 200 件" in summary
    assert "スキップ: 800 件" in summary
    assert "10.0 件/秒" in summary
    assert "1次通過(割安候補) 45 件" in summary


def test_batch_metrics_recommendation_summary():
    metrics = BatchMetrics(job_name="Slack Recommendation", total_count=150)
    metrics.start_time = 1700000000.0
    metrics.set_metric("matched_count", 25)
    metrics.set_metric("quota", 15)
    metrics.record_processed(15)
    metrics.record_failed(0)
    channel_counts = {
        "mansion": 5,
        "kodate": 4,
        "tochi": 3,
        "invest_apartment": 2,
        "invest_kodate": 1,
    }
    metrics.set_metric("channel_counts", channel_counts)
    metrics.finish(fixed_end_time=1700000010.0)

    summary = metrics.build_recommendation_slack_summary(
        channel_counts=channel_counts,
        matched_count=25,
        quota=15,
    )

    assert "【お宝物件配信完了】" in summary
    assert "対象候補 150 件" in summary
    assert "基準合致 25 件" in summary
    assert "配信完了 15 件 (上限枠: 15件)" in summary
    assert "マンション: 5 件" in summary
    assert "戸建: 4 件" in summary
    assert "土地: 3 件" in summary
    assert "投資アパート: 2 件" in summary
    assert "投資戸建: 1 件" in summary


def test_batch_metrics_log_banner():
    metrics = BatchMetrics(job_name="ML Training Pipeline", total_count=50000)
    metrics.start_time = 1700000000.0
    metrics.record_processed(45000)
    metrics.record_skipped(5000)
    metrics.finish(fixed_end_time=1700000300.0)  # 300s = 5m

    banner = metrics.build_log_banner(
        title="ML Model Re-Training Pipeline",
        custom_sections=[
            "• 種別別モデル学習結果:\n  - mansion: サンプル 15,000 件 | MdAPE: 11.2% | R²: 0.88",
            "• 保存アーティファクト: 34 個の joblib モデルを models/ に正常保存完了"
        ]
    )

    assert "================================================================================" in banner
    assert "【バッチ実行サマリー: ML Model Re-Training Pipeline】" in banner
    assert "所要時間: 5分0秒" in banner
    assert "対象総数 50,000 件" in banner
    assert "処理完了 45,000 件" in banner
    assert "mansion: サンプル 15,000 件" in banner
    assert "34 個の joblib モデル" in banner
