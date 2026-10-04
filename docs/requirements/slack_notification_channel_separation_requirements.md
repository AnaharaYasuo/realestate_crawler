# Slack通知チャンネル責務分離 要件定義書 (Slack Notification Channel Separation Requirements)

## 1. 背景と課題
現在、価格推定処理（`run_ml_pipeline.py`）開始時のクローラー集約レポートや、一括クローラー実行（`run_all_crawlers.py`）の正常完了サマリー、お宝物件推薦（`send_recommendations.py`）の種別不明フォールバック通知が `#property_alert`（`SLACK_ALERT_PROPERTY_ALERT`）に送信されている。
本来 `#property_alert` は「システム停止・課金ゾンビ・0件取得・致命的タイムアウト」等の緊急アラート専用であるべきだが、正常終了サマリーや推薦フォールバックが混入することで、運用者が真の緊急事態を見落とすノイズ問題が発生している。

## 2. チャンネル責務の明確化
1. **緊急障害アラートチャンネル (`#property_alert` / `SLACK_ALERT_PROPERTY_ALERT`)**:
   - 致命的タイムアウト (`TimeoutError`)、0件取得異常、GCP停止失敗（ゾンビ課金検知）、失敗タスクを含むクローラー実行サマリーのみを送信。
   - 正常系の完了通知や進捗サマリーの送信を全面禁止。
2. **開発・日次パイプライン運用レポートチャンネル (`#dev-agent` / `SLACK_DEV_CHANNEL`)**:
   - 全タスク集約レポート（正常時）、クローラー完了サマリー（正常時）、スクレイピング検証結果、MLバルク評価進捗・完了、推薦配信完了サマリー、日次予測精度診断、リグレッションテスト結果、種別不明レコメンドフォールバックを集約。
3. **パーサー・データ不整合アラートチャンネル (`#alerts-<種別>`)**:
   - 各物件種別のパース異常・データ不整合アラート。未知種別のフォールバックは `#dev-agent` とする。
4. **お宝物件推薦チャンネル (`#goodproperty-<種別>`)**:
   - 割安・高利回りのお宝物件（Top 1%）推薦。種別判別不能時のフォールバック先は `#dev-agent` とする。

## 3. 受入基準 (Acceptance Criteria)
* [ ] 【基準1】`run_ml_pipeline.py` の `send_aggregated_crawl_report` が、`#property_alert`（`send_crawling_summary_alert`）ではなく `#dev-agent`（`send_dev_report`）経由で送信されること。
* [ ] 【基準2】`run_all_crawlers.py` の実行完了サマリーにおいて、全ジョブ成功時は `#dev-agent`、1件以上の失敗または0件取得を含む場合のみ `#property_alert` へ送信されること。
* [ ] 【基準3】`send_recommendations.py` において、種別判定不能時のフォールバック通知先が `property_alert` から `SLACK_DEV_CHANNEL`（デフォルト: `dev-agent`）へ変更されること。
* [ ] 【基準4】`slack.py` の `get_alert_channel()` において、未知種別のフォールバック先が `property_alert` ではなく `dev-agent`（`SLACK_DEV_CHANNEL`）へ変更されること。
