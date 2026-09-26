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
- Cloud Run API サービス（`realestate-api-${var.environment}`）、クローラーワーカーサービス、および Cloud Run Job（`realestate-crawler-pipeline-${var.environment}`）において、Secret Manager から `NEW_RELIC_LICENSE_KEY` を安全に環境変数として注入すること。
- Cloud Run 実行 SA（`crawler-runner-${var.environment}`）に対し、当該 New Relic ライセンスキー Secret への `roles/secretmanager.secretAccessor` を Terraform（`terraform/iam.tf` の `secret_accessor`）で付与すること。付与漏れにより `SecretsAccessCheckFailed` で新リビジョンが Ready にならない状態を防止する。

### FR-04: Synthetics 外形監視の自動構成
- New Relic NerdGraph (GraphQL API) を介して、本番 API の `/health` エンドポイントに対する死活監視（Ping / Simple Monitor）を自動登録・構成できるスクリプトを提供すること。
- 監視間隔は 5 分、主要ロケーション（東京 `AP_NORTHEAST_1` 等）からのヘルスチェックを可能とすること。

### FR-05: Docker コンテナ & インフラ深層監視
- `newrelic-infra` エージェント構成（`docker-compose.newrelic.yml`）を提供し、ローカル・バッチ実行時および GCE ホスト上の Docker ソケット経由で各コンテナの CPU、メモリ、スロットリング、ネットワーク、I/O メトリクスを常時収集すること。
- ProxySQL および Cloud SQL (MySQL) 接続プール・スロークエリ監視のインテグレーション定義（`nri-mysql`）を提供すること。

### FR-06: GCP Cloud Logging ➔ New Relic ログ統合 (Log in Context)
- Cloud Run サービス（`cloud_run_revision`）、Cloud Run Job（`cloud_run_job`）、Cloud SQL、ProxySQL の GCP Cloud Logging ログを Pub/Sub トピック経由で New Relic Log Management へリアルタイム転送する Terraform 定義（`terraform/new_relic_gcp_integration.tf`）を整備すること。
- APM トレース ID（`trace.id`）との紐付け（Log in Context）により、障害発生時にトレースとログをシームレスに横断分析可能とすること。
- Deploy 用 GitHub Actions SA（`github-actions-crawler@...`、`secrets.GCP_SERVICE_ACCOUNT` と同一）に `roles/logging.configWriter` および `roles/pubsub.admin` を付与し、`google_logging_project_sink` の `logging.sinks.create` と sink writer の Pub/Sub topic IAM 更新が CI Terraform Apply で成功すること（`roles/editor` だけでは不足）。

### FR-07: GenAI / LLM 監視 (New Relic AI Monitoring)
- 不動産パース時における Gemini 等の LLM 呼び出しに対し、プロンプト/完了トークン数、推論レイテンシ、推論コスト（推定 USD）、および成否ステータスを New Relic カスタムイベント（`LlmEvent`）またはメトリクスとして記録する共通ヘルパーを提供すること。
- LLM API 呼び出しのレート制限（HTTP 429）やエラー発生時に New Relic へエラーレポート（`notice_error`）すること。

### FR-08: デプロイ変更追跡 (Change Tracking)
- CI/CD（GitHub Actions）や手動デプロイ時に、デプロイバージョン、Git コミットハッシュ、変更ログ、実行者を New Relic NerdGraph Change Tracking API へ通知するスクリプト（`notify_new_relic_deployment.py`）を提供すること。
- リリース前後のエラー率やレイテンシ変動を New Relic ダッシュボード上で自動マーキング・追跡可能とすること。

### FR-09: クローラー特化 NRQL アラートルール自動構成
- クローラー運用に特化した New Relic アラートポリシー（`RealEstate Crawler Operations`）および以下の NRQL アラート条件をプロビジョニングする自動化スクリプト（`setup_new_relic_crawler_alerts.py`）を提供すること:
  1. **ゼロ件取得失敗 (Zero-Count Failure)**: クロール結果が 0 件のジョブの検出。
  2. **パース性能劣化 (Parse Performance Degradation)**: 静的パーサーが 1.0 秒/件を超過した場合の警告。
  3. **対象サイト拒絶急増 (Target Site 403/429 Spike)**: スクレイピングブロックやレート制限の急増。
  4. **コンテナリソース高負荷 (Container High CPU/Memory)**: メモリ使用率 85% 超の OOM 予兆検知。

### FR-10: パイプライン実行・バッチクローラー APM & メトリクス計装
- Cloud Run Job エントリーポイント（`run_pipeline.py`）およびバッチクローラー（`run_all_crawlers.py`）の起動時に `init_new_relic()` を呼び出し、APM エージェントを初期化すること。
- 各クロールジョブの終了時（正常終了・エラー・タイムアウト時）に `record_crawler_metrics()` を呼び出し、サイト別・種別別の取得件数、実行時間、ステータスを New Relic カスタムイベント（`CrawlerExecution`）へ送信すること。

## 4. 非機能要件
- **NFR-01 (セキュリティ)**: ライセンスキー・API キー等の機密情報はリポジトリへコミットせず、`.env` および GCP Secret Manager にて秘匿管理すること。
- **NFR-02 (可用性・耐障害性)**: New Relic 連携の失敗（ネットワーク障害、キー無効等）によって、クローラーや API のコア機能が起動不能に陥らない（Graceful Degradation）こと。
- **NFR-03 (パフォーマンス)**: エージェント導入およびメトリクス送信によるオーバーヘッドを最小限（1件あたり数ミリ秒以内）に抑えること。
- **NFR-04 (API タイムアウト保証)**: New Relic NerdGraph / REST API への通信は有限時間タイムアウト（最大10秒、NFR-021）を遵守すること。

## 5. 受入基準 (Acceptance Criteria)
- [x] 【基準1】Python APM エージェント（newrelic）が設定され、環境変数が有効な場合に自動計装されること
- [x] 【基準2】Terraform および Secret Manager 定義に New Relic ライセンスキー連携が定義され、Cloud Run サービスへ安全に注入可能であること
- [x] 【基準3】New Relic Synthetics（外形監視・死活ヘルスチェック）設定スクリプト/定義が存在し、API エンドポイント監視が自動構成できること
- [ ] 【基準4】Docker コンテナおよび DB/ProxySQL 監視設定ファイル（`docker-compose.newrelic.yml`）が整備されていること
- [ ] 【基準5】GCP Cloud Logging ➔ New Relic 転送ログルーター Terraform 定義が存在すること
- [ ] 【基準6】GenAI / LLM パース時のトークン数・レイテンシ・コスト計測連携ヘルパーが実装されていること
- [ ] 【基準7】デプロイ通知スクリプト（Change Tracking）およびクローラー特化 NRQL アラート設定スクリプトが実装されていること
- [ ] 【基準8】SDD 仕様ドキュメント（要件定義・基本設計・内部設計）が同期更新されていること
- [ ] 【基準9】単体テスト・ローカル静的解析（SonarCloud / CodeRabbit CLI）を 100% 通過すること
