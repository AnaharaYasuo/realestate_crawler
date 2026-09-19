---
name: auto-healing
description: 直近のクローリング監視や全アラートSlackチャンネルで検出されたパースエラー・0件取得異常を、AIが自律的に調査・修正し、修正後に共通の /regression-test ワークフローを呼び出して復旧・修復（Self-Healing）するためのスキルです。
---

# 自律型AIパーサー自己修復 (Self-Healing) スキル

このスキルは、クローリング監視アラートや0件取得検出時（またはユーザーからの `/auto-heal` 指示時）にトリガーされ、人手を介さずに全自動でバグ修正および後修復検証を行う実行ガイドラインです。

## 実行ステップ

### 1. アラート調査・コンテナログ点検 ＆ 原因特定
* 把握した問題・アラート一覧をまず整理し、最初（Step 1）に Slack チャンネルへ投稿・報告すること。
* 実際に存在するすべてのアラート系 Slack チャンネル（`#alerts-mansion`, `#alerts-kodate`, `#alerts-tochi`, `#alerts-invest`, `#alerts-invest-apartment`, `#alerts-invest-kodate`, `#property_alert`, `#dev-agent`）の直近投稿およびスレッドを漏れなくすべてチェック。
* **メインコンテナログの点検**: `realestate_crawler-app-1`（`docker logs --tail 300 realestate_crawler-app-1` 等）のログを巡回点検し、`QueuePool overflow` (DB接続漏れ/タイムアウト)、`500 Internal Server Error`、未捕捉例外、パース失敗エラー、**パーサー未整備エラー（`[PARSER_UNAVAILABLE]`, `[PARSER_NOT_FOUND]`）**が発生していないかを自動検知。
* 0件取得（Zero-Count Failure）になっているサイト・モデル、およびパースエラーを起こしているページを特定。
* **パーサー未整備エラーの新規作成タスク化**: `[PARSER_UNAVAILABLE]` が検知された場合、`CandidatePropertyUrl` テーブルから対象ドメイン・URL・リクエスト頻度を抽出し、新規パーサー開発対象（Backlog）として自律的に開発タスクを起票・実装する。
* 対象のパーサー、ルート、モデル、スタートURL、または DB コネクション管理コードを正しく修正。



### 2. リグレッションテストの呼び出し
* 修正完了後、スキル/ワークフロー `/regression-test` を呼び出し、セキュリティ走査・動的二段階検証・処理時間アサーション・pytest全パスを確認すること。
