# New Relic 統合監視 要件定義書

## 1. 概要
本要件定義書は、不動産クローラーシステム（Cloud Run API、クローラーワーカー、Slackエージェント）における New Relic APM（アプリケーション・パフォーマンス・モニタリング）、Synthetics（外形監視・死活ヘルスチェック）、および GCP インフラ（Secret Manager、Cloud Run）統合監視の仕様と受入基準を定義する。

## 2. 背景・目的
- **背景**: 不動産クローラーおよび価格推定 API は Cloud Run サーバーレス環境で稼働しており、レイテンシのスパイク、DB クエリの遅延、メモリ使用量、外部ポータルスクレイピング時のエラー等を統合的かつリアルタイムに可視化・アラート通知する仕組みが不足していた。
- **目的**: New Relic を導入し、以下の3本柱で一元監視を実現する:
  1. **Python APM**: トランザクション処理時間、DB・外部HTTP呼び出し、エラーの自動トレース。
  2. **GCP Cloud Run / Terraform 連携**: Secret Manager によるライセンスキーの安全な一元管理と各 Cloud Run サービスへの自動注入。
  3. **New Relic Synthetics (外形監視)**: 公開 API エンドポイント（`/health`）に対する定期死活・レイテンシ監視の自動化。

## 3. 機能要件

### FR-01: ヘルスチェックエンドポイントの提供
- `/` および `/health` に対する GET リクエストに対し、HTTP 200 OK かつ JSON 形式（`status: ok`, `timestamp`）で即座に応答すること。
- API キー認証のバイパス対象とし、外部ヘルスチェッカーや Synthetics からの監視を妨げないこと。

### FR-02: Python APM エージェント自動計装
- アプリケーション起動時に `NEW_RELIC_LICENSE_KEY` 環境変数が存在する場合、`newrelic.agent.initialize()` により自動的に APM 計装を開始すること。
- 環境変数が未設定の場合（ローカル開発・テスト時など）は、エラー終了することなく透過的にスキップ（フォールバック）すること。
- アプリケーション名（`NEW_RELIC_APP_NAME`）および分散トレーシング（`NEW_RELIC_DISTRIBUTED_TRACING_ENABLED`）の設定をサポートすること。

### FR-03: Terraform ＆ Secret Manager 管理
- Secret Manager に `realestate-new-relic-license-key-${var.environment}` を定義すること。
- Cloud Run API サービス（`realestate-api-${var.environment}`）およびクローラーサービスにおいて、Secret Manager から `NEW_RELIC_LICENSE_KEY` を安全に環境変数として注入すること。

### FR-04: Synthetics 外形監視の自動構成
- New Relic NerdGraph (GraphQL API) を介して、本番 API の `/health` エンドポイントに対する死活監視（Ping / Simple Monitor）を自動登録・構成できるスクリプトを提供すること。
- 監視間隔は 5 分、主要ロケーション（東京 `AP_NORTHEAST_1` 等）からのヘルスチェックを可能とすること。

## 4. 非機能要件
- **NFR-01 (セキュリティ)**: ライセンスキー等の機密情報はリポジトリへコミットせず、`.env` および GCP Secret Manager にて秘匿管理すること。
- **NFR-02 (可用性・耐障害性)**: New Relic 連携の失敗（ネットワーク障害、キー無効等）によって、クローラーや API のコア機能が起動不能に陥らない（Graceful Degradation）こと。
- **NFR-03 (パフォーマンス)**: エージェント導入によるオーバーヘッドを最小限に抑えること。

## 5. 受入基準 (Acceptance Criteria)
- [x] 【基準1】Python APM エージェント（newrelic）が設定され、環境変数が有効な場合に自動計装されること
- [x] 【基準2】Terraform および Secret Manager 定義に New Relic ライセンスキー連携が定義され、Cloud Run サービスへ安全に注入可能であること
- [x] 【基準3】New Relic Synthetics（外形監視・死活ヘルスチェック）設定スクリプト/定義が存在し、API エンドポイント監視が自動構成できること
- [x] 【基準4】SDD ドキュメント（要件定義・外部設計・内部設計）が同期更新されていること
- [x] 【基準5】ユニットテスト・回帰テストを通過すること
