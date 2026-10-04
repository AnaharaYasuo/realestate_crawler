# Slack通知チャンネル責務分離 基本設計書 (Slack Notification Channel Separation Basic Design)

## 1. 概要
本設計書は、Issue #688 に基づき、各種通知が適切なSlackチャンネルへ振り分けられるよう、送信先ロジックの再定義と標準化を行う。

## 2. チャンネルマッピング設計

### 2.1 チャンネル構成と役割
| チャンネル分類 | チャンネル名 / 環境変数 | 対象メッセージ種別 | 障害時動作 |
|---|---|---|---|
| **緊急アラート** | `#property_alert`<br>`SLACK_ALERT_PROPERTY_ALERT` | ・パイプライン全体タイムアウト<br>・リソース停止失敗 (GCPゾンビ課金)<br>・クローラー障害含むサマリー (失敗ジョブ > 0) | アプリログに `logger.error` 出力 |
| **開発・運用レポート** | `#dev-agent`<br>`SLACK_DEV_CHANNEL` | ・全タスク集約レポート (正常時)<br>・クローラー正常完了サマリー (失敗ジョブ == 0)<br>・データ検証 & クレンジング結果<br>・Auto-Heal 指示書<br>・MLバルク推論進捗・完了<br>・お宝物件推薦配信サマリー<br>・日次予測診断・AIインサイト<br>・種別不明お宝物件フォールバック | 通常ログ出力 |
| **パーサー障害** | `#alerts-<種別>`<br>`SLACK_ALERT_<種別>` | ・各物件種別のパースエラー、欠損値異常 | アプリログに `logger.error` 出力 |
| **お宝物件推薦** | `#goodproperty-<種別>`<br>`SLACK_RECOMMEND_<種別>` | ・Top 1% お宝物件レコメンド | 通常ログ出力 |

### 2.2 処理別ルーティング詳細
1. **`run_ml_pipeline.py` (`send_aggregated_crawl_report`)**:
   - `send_crawling_summary_alert` の呼び出しを `send_dev_report` へ変更。
   - ただし、集約結果で失敗タスクが存在する場合は、サマリーを `#dev-agent` に送ると同時に `#property_alert` にも警告送信。
2. **`run_all_crawlers.py`**:
   - 終了時サマリーについて、`failed_crawlers` が 0 件の場合は `send_dev_report` で `#dev-agent` に通知。
   - `failed_crawlers` が 1 件以上ある場合は `send_crawling_summary_alert` で `#property_alert` に通知。
3. **`send_recommendations.py`**:
   - `_resolve_target_channel()` の最終フォールバック先を `os.getenv("SLACK_DEV_CHANNEL") or "dev-agent"` とする。
4. **`package/utils/slack.py`**:
   - `get_alert_channel(property_type)` の最終フォールバック先を `os.getenv("SLACK_DEV_CHANNEL") or "dev-agent"` とする（未知種別アラートが property_alert を汚染するのを防ぐ）。
