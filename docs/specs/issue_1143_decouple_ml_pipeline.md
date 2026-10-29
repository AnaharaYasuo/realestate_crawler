# MLパイプライン独立スケジュール化およびクローラー疎結合化仕様書 (Issue #1143)

## 1. 概要 (Overview)
これまで Cloud Workflows (`realestate-daily-pipeline-prod`) 内において、クローラー実行と後続の ML価格推定・割安物件公開（`realestate-ml-pipeline-prod`）が直列に結合されていた。
このため、外部サイトの不調・タイムアウト等によってクローラータスクが 1 つでも異常終了すると、パイプライン全体が中断され、すでに収集・蓄積されている物件の推定や割安物件の Slack 公開が行われないという構造的課題（密結合）が存在していた。

本改修では「B案（クローリングと ML価格推定・割安物件公開の完全分離・時間差独立スケジュール化）」を採用し、クローラーの成否ステータスに一切左右されず、毎朝確実に割安物件が推定・公開される疎結合アーキテクチャを実現する。

## 2. 要件定義 (Requirements)

1. **独立した Cloud Scheduler による日次 ML パイプライン実行**:
   - `realestate-ml-pipeline-daily-prod` の `paused = false`（有効化）とする。
   - クローラーの最大許容時間（最長 4 時間）を十分に考慮し、クローラー完了後の毎朝 **05:10 JST (20:10 UTC)** に起動する。
   - cron 式: `10 20 * * *` (UTC)

2. **タイムライン設計と重複・競合の防止**:
   - **01:00 JST (16:00 UTC)**: `Cloud Scheduler (realestate-crawler-daily-prod)` がクローラーを開始。
   - **05:10 JST (20:10 UTC)**: `Cloud Scheduler (realestate-ml-pipeline-daily-prod)` が ML 価格推定 & お宝物件配信を開始。
   - **09:00 JST (00:00 UTC)**: Cloud SQL 日次自動バックアップ（競合なし）。
   - Safety-Net は 24 時間毎時稼働し、パイプライン終了後のリソース（ProxySQL）解放を担保する。

3. **Terraform 定義および仕様ドキュメントの整合性維持**:
   - `terraform/scheduler.tf`: `ml_pipeline_daily_trigger` の `paused` を `false` に変更。
   - `terraform/variables.tf`: `ml_pipeline_schedule_cron` のデフォルト値を `"10 20 * * *"` に更新。
   - 既存の単体テスト（`test_crawler_ml_split_549.py`, `test_crawler_timeout_4h_635.py` 等）を新仕様に合わせて更新。

## 3. テスト計画
- 単体テスト（pytest）による cron 設定整合性、デッドライン関係式のパス確認。
- Terraform 構文検証（terraform fmt / validate 等）。
