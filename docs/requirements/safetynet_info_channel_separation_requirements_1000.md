# 要件定義: Safety-Net 情報通知の dev-agent チャンネル分離 (Issue #1000)

## 1. 背景と課題
現在、`src/crawler/scripts/ensure_resources_stopped.py`（Safety-Net）において、以下の2種類の正常継続通知が `send_slack_alert()` 経由でアラート用チャンネル（`SLACK_ALERT_PROPERTY_ALERT` / デフォルト `property_alert`）に送信されている。
1. **アクティブ外部クエリ通信検知時の起動継続**:
   - `【Safety-Net】アクティブな外部クエリ通信を検知したためProxySQLの起動を継続しました`
2. **クローラー/MLパイプライン正常実行中の起動継続**:
   - `【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました`

これらは障害・停止漏れ検知（ゾンビ課金アラート、強制停止失敗などの警告・緊急通報）ではなく「正常稼働継続」を知らせる情報（INFO）通知であるため、アラート専用チャンネルを汚染し運用監視上のノイズとなっていた。

## 2. 要件仕様
1. **情報通知（INFO）の送信先分離**:
   - Safety-Net の正常継続通知（外部クエリ通信検知、ジョブ正常実行中）は、アラートチャンネルではなく、開発・レポート用チャンネル（`SLACK_DEV_CHANNEL`、デフォルト `dev-agent`）へ送信する。
   - `send_slack_info` または `send_slack_alert(message, channel=...)` 等を用い、明示的に `SLACK_DEV_CHANNEL`（フォールバック: `dev-agent`）をターゲットとする。
2. **真のアラート（WARNING / ERROR）の送信先維持**:
   - ゾンビ課金検知（停止漏れ検知）、ジョブ異常超過検知、強制停止失敗等の警告・緊急メッセージは、従来通りアラートチャンネル（`SLACK_ALERT_PROPERTY_ALERT` / `property_alert`）へ送信する。
3. **インフラ・環境変数整合性**:
   - Safety-Net の Cloud Run Job 定義（`terraform/cloud_run_job.tf`）に `SLACK_DEV_CHANNEL` 環境変数が渡されていることを保証する。
4. **テスト・検証**:
   - Safety-Net のユニットテスト（`test_ensure_resources_stopped.py`, `test_safetynet_traffic_check_901.py` 等）において、情報通知が `SLACK_DEV_CHANNEL` / `dev-agent` を対象として送信されることを検証する。
