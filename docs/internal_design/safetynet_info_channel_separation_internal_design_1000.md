# 内部設計書: Safety-Net 情報通知の dev-agent チャンネル分離 (Issue #1000)

## 1. 変更アーキテクチャ

### 1.1 通知関数の設計 (`src/crawler/scripts/ensure_resources_stopped.py`)
Safety-Net スクリプト内における Slack 送信処理:
- `send_slack_info(message: str)` 関数を新設（または `send_slack_alert(message, channel=...)` を利用）。
  - 送信先: `os.environ.get("SLACK_DEV_CHANNEL") or "dev-agent"`
- 以下の正常継続情報通知は `send_slack_info()` を使用:
  1. `check_and_stop_proxysql_instance`:
     - `info_msg`（クローラー/MLパイプライン正常実行中の継続通知）
     - `info_msg`（アクティブな外部クエリ通信検知時の継続通知）
  2. `check_and_stop_proxysql_mig`:
     - `info_msg`（クローラー/MLパイプライン正常実行中の継続通知）

### 1.2 アラート通知の維持
以下のメッセージは引き続き `send_slack_alert()`（宛先: `SLACK_ALERT_PROPERTY_ALERT` / `property_alert`）を使用:
- `【ゾンビ課金アラート】ProxySQL停止漏れ検知`
- `【ゾンビ課金アラート】ジョブ異常超過検知`
- `【ゾンビ課金アラート】ProxySQL MIG停止漏れ検知`
- `【緊急】強制停止処理で一部失敗が発生しました`
- `【緊急】ProxySQL MIGの強制停止に失敗しました`
- その他 API エラー・停止失敗の警告

### 1.3 Terraform 設定 (`terraform/cloud_run_job.tf`)
- Safety-Net Cloud Run Job（`realestate-safety-net`）のコンテナ環境変数に以下を追加:
  ```hcl
  env {
    name  = "SLACK_DEV_CHANNEL"
    value = var.slack_dev_channel # または "dev-agent" (既存の他ジョブと同一定義)
  }
  ```

## 2. テスト設計
- `src/crawler/tests/unit/test_safetynet_traffic_check_901.py`:
  - `send_slack_info` が呼ばれ、適切なチャンネルまたは引数で呼び出されることを検証。
- `src/crawler/tests/test_ensure_resources_stopped.py`:
  - 正常実行継続通知時に `send_slack_info` が呼ばれ、`send_slack_alert` は呼ばれない（アラートチャンネルには通知されない）ことを検証。
