# Slack通知チャンネル責務分離 内部設計書 (Slack Notification Channel Separation Detailed Design)

## 1. モジュール別改修仕様

### 1.1 `src/crawler/package/utils/slack.py`
- `get_alert_channel(property_type: str) -> str`:
  - 変更前:
    ```python
    return os.getenv("SLACK_ALERT_PROPERTY_ALERT") or os.getenv("SLACK_CHANNEL_ID") or "property_alert"
    ```
  - 変更後:
    ```python
    return os.getenv("SLACK_DEV_CHANNEL") or os.getenv("SLACK_CHANNEL_ID") or "dev-agent"
    ```

### 1.2 `src/crawler/scripts/ops/run_ml_pipeline.py`
- `send_aggregated_crawl_report(execution_date: datetime.date | None = None) -> bool`:
  - インポートに `send_dev_report` を追加。
  - レポート本文送信先を `send_dev_report(aggregated["slack_message"])` とする。
  - もし `aggregated["failed_jobs"] > 0` の場合は、追加で `send_crawling_summary_alert(aggregated["slack_message"])` を呼び出し、障害発生時のみ `#property_alert` へ通報する。

### 1.3 `src/crawler/scripts/ops/run_all_crawlers.py`
- クローラー実行完了サマリー送信部:
  - 終了時、`failed_crawlers` が空（全件成功）の場合は `send_dev_report` を呼び出す。
  - `failed_crawlers` に1件でも失敗がある場合は `send_crawling_summary_alert` を呼び出す。

### 1.4 `src/crawler/scripts/ops/send_recommendations.py`
- `_resolve_target_channel(prop, property_type: str) -> str`:
  - 最終フォールバック先:
    ```python
    return os.getenv("SLACK_RECOMMEND_CHANNEL_ID") or os.getenv("SLACK_DEV_CHANNEL") or "dev-agent"
    ```
