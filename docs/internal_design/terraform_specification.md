# Terraform インフラストラクチャ詳細設計書 (Terraform Internal Specification)

## 1. 構成概要
本設計書は、GCPリソース群を宣言的に管理する Terraform コードのファイル構成、変数仕様、出力仕様、リソース依存関係を定義する。

### 1.1 ディレクトリ構成 (`terraform/`)
```
terraform/
├── main.tf                    # プロバイダー定義 (google, google-beta), バージョン固定, backend設定
├── variables.tf               # 入力変数定義 (型, デフォルト値, 説明)
├── outputs.tf                 # 出力値 (Job名, DB Private IP, GCSバケット名, NAT固定IP, ProxySQL ILB IP)
├── terraform.tfvars.example   # 設定パラメータの雛形
├── network.tf                 # VPC, サブネット, Serverless VPC Access, Cloud Router, Cloud NAT
├── storage.tf                 # Cloud Storage (物件画像・エビデンス)
├── database.tf                # Cloud SQL for MySQL 8.0, ユーザー, データベース
├── proxysql.tf                # ProxySQL コネクションプーリング (MIG e2-micro x 2, ILB, Health Check, FW)
├── secrets.tf                 # Secret Manager (DB接続情報, Slackトークン)
├── artifact_registry.tf       # Artifact Registry Docker リポジトリ
├── iam.tf                     # 実行用 Service Account, IAM Role バインディング
├── cloud_run_job.tf           # Cloud Run Jobs (Dispatcher Job, ML Pipeline Job, DB移行, セーフティネット)
├── cloud_run_service.tf       # Cloud Run Service (Slack Agent 常時受付)
├── cloud_run_crawler_service.tf # Cloud Run Service (Crawler Worker 分散スクレイピング)
├── cloud_tasks.tf             # Cloud Tasks (crawler-tasks Queue, レート・並列制御)
├── scheduler.tf               # Cloud Scheduler (日次定期キック)
├── budget.tf                  # Cloud Billing 予算アラート (50%, 80%, 100%, 120%予測)
└── alerting.tf                # Cloud Monitoring & Logging 監視アラート (MySQL認証拒否, サーバエラー, コネクション枯渇)
```



---

## 2. 変数定義仕様 (`variables.tf`)

| 変数名 | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| `project_id` | `string` | `"sumifu"` | GCPプロジェクトID |
| `region` | `string` | `"asia-northeast1"` | リソース配置リージョン（東京） |
| `zone` | `string` | `"asia-northeast1-a"` | デフォルトゾーン |
| `environment` | `string` | `"prod"` | 環境識別子 (`dev` / `stg` / `prod`) |
| `db_tier` | `string` | `"db-f1-micro"` | Cloud SQL マシンスペック (`db-f1-micro` または `db-g1-small` / `db-custom-2-7680`) |
| `db_name` | `string` | `"real_estate"` | MySQL データベース名 |
| `db_user` | `string` | `"sumifu"` | MySQL ユーザー名 |
| `crawler_cpu` | `string` | `"2"` | Cloud Run Jobs CPU コア数 |
| `crawler_memory` | `string` | `"4Gi"` | Cloud Run Jobs メモリ割り当て |
| `crawler_timeout` | `string` | `"7200s"` | クローラー Cloud Run Job の 1 タスクあたりのタイムアウト（2 時間。Cloud Run Jobs の上限は 24 時間 = `86400s` だが、Safety-Net の hung 判定 7800s・`ml_pipeline_schedule_cron`・バックアップ開始時刻と整合させるため validation で `1s`〜`7200s` に制限）。同値の秒数を環境変数 `CLOUD_RUN_JOB_TIMEOUT_SEC` としてジョブに渡し、`run_pipeline.py` の内部締め切りと一致させる（Issue #550） |
| `schedule_cron` | `string` | `"0 16 * * *"` | Cloud Scheduler 実行cron式（UTC 16:00 = JST 01:00） |
| `ml_pipeline_schedule_cron` | `string` | `"10 18 * * *"` | ML Pipeline Job 起動cron式（UTC 18:10 = JST 03:10）。`schedule_cron` + `crawler_timeout`（最遅 18:00 UTC）より後であること（Issue #550） |

---

## 3. リソース詳細設計

### 3.1 ネットワーク & NAT (`network.tf`)
- `google_compute_network`: カスタムサブネット型 VPC
- `google_compute_subnetwork`: VPC コネクタ用およびリソース用サブネット（VPC Flow Logs 有効化済）
- `google_vpc_access_connector`: Cloud Run から VPC への接続インターフェース（`e2-micro`, min: 2, max: 3）
- `google_compute_router`: Cloud NAT 制御用ルーター
- `google_compute_address`: 送信元固定用の静的外部 IP アドレス
- `google_compute_router_nat`: 静的外部 IP を紐付けた NAT ゲートウェイ（全サブネットからの送信パケットのIP固定）

### 3.2 データベース (`database.tf`)
- `google_compute_global_address`: 内部接続用プライベート IP 範囲
- `google_service_networking_connection`: Google プライベート サービス アクセス接続
- `google_sql_database_instance`:
  - データベースバージョン: `MYSQL_8_0`
  - プライベート IP 有効 (`private_network = google_compute_network.id`)
  - パラメータ: `character_set_server = utf8mb4`, `collation_server = utf8mb4_unicode_ci`, `max_connections = 1000`
  - セキュリティフラグ: `cloudsql_iam_authentication = on`, `local_infile = off`, `skip_show_database = on`
  - 認証プラグイン: 非推奨の `default_authentication_plugin = "mysql_native_password"` を撤廃し、MySQL 8.0 標準の `caching_sha2_password` を適用（Issue #572）
  - バックアップ設定: 有効（毎日自動バックアップ、開始 `20:00` UTC = JST 05:00。クローラー最遅終了 18:00 UTC・ML Pipeline Job 最遅終了 19:10 UTC 以降。Issue #550）
- `google_sql_user.db_user`: アプリケーション接続用 MySQL ユーザー (`var.db_user`, 認証プラグイン: `caching_sha2_password`)
- `google_sql_user.monitor_user`: ProxySQL ヘルスチェック監視専用 MySQL ユーザー (`name = "monitor"`, 最小 USAGE 権限, 認証プラグイン: `caching_sha2_password`)
- `random_password.db_monitor_password`: 監視用ランダムパスワード (24桁、Secret Manager 格納)


### 3.3 コンピュート (`cloud_run_job.tf`, `cloud_run_service.tf`, `cloud_run_api_service.tf`)
- `google_cloud_run_v2_job` (クローラーバッチ `crawler_pipeline_job`):
  - 実行イメージ: `${region}-docker.pkg.dev/${project_id}/realestate-crawler/crawler:latest`
  - 実行引数: `["python", "src/crawler/scripts/ops/run_pipeline.py"]`
  - 共有メモリ設定: in-memory `emptyDir` ボリュームを `/dev/shm` にマウント（Playwright クラッシュ防止）
  - VPC コネクタ接続: `vpc_access.egress = ALL_TRAFFIC` (全外部通信を Cloud NAT 経由にして固定IP化)
  - データベース接続: ProxySQL (`google_compute_address.proxysql_ip.address:6033` / `10.0.0.10:6033`) へダイレクトルーティング。環境変数 `DB_POOL_SIZE = "2"`, `DB_MAX_OVERFLOW = "1"` により各ワーカーのアイドル接続を抑制
  - 環境変数: Secret Manager からシークレット参照（`value_source`）、Slack 通知先チャンネル ID 設定 (`SLACK_CHANNEL_ID`, `SLACK_DEV_CHANNEL`, `SLACK_ALERT_PROPERTY_ALERT`, `SLACK_RECOMMEND_*`)
- `google_cloud_run_v2_job` (DBマイグレーション `migrate_job`):
  - DDL スキーマ更新のため、直接 Cloud SQL (`google_sql_database_instance.mysql_instance.private_ip_address:3306`) に接続
- `google_cloud_run_v2_service` (`slack_agent_service`, `api_service`):
  - データベース接続: ProxySQL (`google_compute_address.proxysql_ip.address:6033` / `10.0.0.10:6033`) へダイレクトルーティング。環境変数 `DB_POOL_SIZE = "5"`, `DB_MAX_OVERFLOW = "2"` 設定

### 3.4 コネクションプーリング層 (`proxysql.tf`)
- `google_service_account`: ProxySQL インスタンス専用の最小権限サービスアカウント (`proxysql-sa-${var.environment}`)
- `google_compute_address.proxysql_ip`:
  - サブネット内の静的プライベート IP (`10.0.0.10`)。ILB を用いず直接名前解決・ルーティング可能とする。
- `google_compute_instance.proxysql_instance`:
  - マシンタイプ: `var.proxysql_machine_type` (初期値: `e2-micro`。トラフィック増加時は垂直スケールアップ)
  - ゾーン: `${var.region}-a`
  - OSイメージ: `debian-cloud/debian-12`
  - ネットワーク: `google_compute_subnetwork.subnet.id`、静的内部 IP (`google_compute_address.proxysql_ip.address`)、外部IPなし
  - タグ: `["proxysql"]`
  - 管理認証情報 (`admin_variables`): `random_password.proxysql_admin_password` により生成されたランダムパスワードを適用
  - バックエンド監視設定 (`mysql_variables`): `monitor_username = "monitor"`, `monitor_password = "${random_password.db_monitor_password.result}"` を設定
  - バックエンド接続暗号化 (`mysql_servers`): `use_ssl = 1` を指定し、Cloud SQL への TLS 暗号化接続を有効化。これにより RSA 公開鍵交換不要で `caching_sha2_password` をサポート（Issue #572）
  - 起動スクリプト (`metadata_startup_script`): ProxySQL の自動セットアップ、Cloud SQL プライベート IP へのバックエンド登録、コネクション多重化設定、ポート 6033/6032 のリスニング開始

    - DPKG/APT ロック競合対策 (Issue #518): `wait_for_apt_locks` 関数で `/var/lib/dpkg/lock-frontend`・`/var/lib/dpkg/lock`・`/var/lib/apt/lists/lock` を `fuser` で監視し、解放まで 2 秒間隔で待機。待機予算 600 秒は `apt_retry` 1 呼び出し内の全試行で累積共有（`APT_LOCK_WAITED`、試行ごとにリセットしない）し、予算消化後も即時失敗させず `apt-get -o DPkg::Lock::Timeout=120` のロック待機に委ねる（永続ロック時の最悪所要: 600 + 5×120 + 75 秒 ≒ 21 分）
    - `apt_retry` 関数で `apt-get` を最大 5 回、指数バックオフ（5, 10, 20, 40 秒）でリトライし、`set -euo pipefail` 下での一時的競合・通信瞬断による即死を防止
    - `apt-get update` は既定では一部リポジトリの一時的な取得失敗でも終了コード 0 を返し得るため、全 `update` 呼び出しに `--error-on=any` を指定して取得失敗を非ゼロ終了させ、`apt_retry` の再試行対象とする（古い・欠落した索引での後続 `install` を防止）
- `google_compute_firewall`:
  - `allow-proxysql-internal`: VPC 内部サブネット (`10.0.0.0/24`) からのポート 6033 アクセス許可
- **ILB (Forwarding Rule / Backend Service / Health Check) の廃止**:
  - 常時課金が発生する転送ルールを完全削除し、Direct VPC Egress から ProxySQL の静的内部 IP への直結により月額固定費を削減。

### 3.5 コンテナリポジトリ & ライフサイクル設計 (`artifact_registry.tf`)
- `google_artifact_registry_repository` (`crawler_repo`):
  - リポジトリID: `realestate-crawler-${var.environment}`
  - フォーマット: `DOCKER`
  - リージョン: `var.region` (`asia-northeast1`)
  - クリーンアップポリシー設定 (`cleanup_policies`):
    - `cleanup_policy_dry_run`: `false` (本番削除有効)
    - ポリシー1 (`keep-recent-3`, `KEEP`): `most_recent_versions.keep_count = 3`。最新3世代のコンテナイメージのみを保持
    - ポリシー2 (`delete-untagged`, `DELETE`): `condition.tag_state = "UNTAGGED"`。新イメージ push でタグが外れた過去の中間・不要イメージを自動パージ

### 3.8 ログ監視・アラートポリシー設計 (`alerting.tf`)
- **ログベースメトリクス (`google_logging_metric`)**:
  - `mysql_access_denied_metric`: フィルタ `resource.type="cloudsql_database" AND (textPayload =~ "Access denied for user" OR textPayload =~ "MY-010926")`。通常 NOTICE 扱いされる MySQL 認証拒否を数値化
  - `mysql_error_log_metric`: フィルタ `resource.type="cloudsql_database" AND (severity >= ERROR OR textPayload =~ "\\[ERROR\\]")`。MySQL エラーログ内の致命的エラーを捕捉
  - `mysql_too_many_connections_metric`: フィルタ `resource.type="cloudsql_database" AND (textPayload =~ "Too many connections" OR textPayload =~ "MY-010048")`。接続上限飽和を即時捕捉
- **Cloud Monitoring アラートポリシー (`google_monitoring_alert_policy`)**:
  - `mysql_access_denied_alert`: 重大度 `ERROR`。認証失敗カウント > 0（期間: 60秒）で即時発報
  - `mysql_error_log_alert`: 重大度 `ERROR`。MySQL サーバエラーログ検知で発報
  - `mysql_too_many_connections_alert`: 重大度 `CRITICAL`。接続上限到達で発報
  - `proxysql_unhealthy_alert`: 重大度 `ERROR`。`condition_matched_log` によるログ監視。ProxySQL MIG (`gce_instance_group_manager`) 異常インスタンス検知（UNHEALTHY）時に発報
  - 通知チャンネル: メール (`var.alert_email`) および Pub/Sub トピック (`google_pubsub_topic.budget_alert_topic`) へ集約
- **Pub/Sub 通知チャンネルの発行権限 (Issue #543)**:
  - `google_project_service_identity.monitoring_notification_agent`（`google-beta`、`service = "monitoring.googleapis.com"`）: Monitoring 通知サービスエージェント `service-<PROJECT_NUMBER>@gcp-sa-monitoring-notification.iam.gserviceaccount.com` を明示的に生成・取得する。新規プロジェクトで通知チャンネル作成前にエージェントが未作成でも IAM 付与が失敗しないようにするため。
  - `google_pubsub_topic_iam_member.monitoring_notification_publisher`: 上記エージェント（`google_project_service_identity.monitoring_notification_agent.email`。メールアドレスはハードコードしない）に `budget_alert_topic` 限定で `roles/pubsub.publisher` を付与する（`google_project_iam_member` / `google_project_iam_binding` によるプロジェクトレベル付与はしない）。未付与だと通知発行が `PERMISSION_DENIED` となる。
  - `google_pubsub_topic_iam_member.github_actions_budget_topic_iam`: Deploy SA（`var.github_actions_sa_email`）に `budget_alert_topic` 限定でカスタムロール `projects/${var.project_id}/roles/pubsubTopicIamManager` を付与し、CI の Terraform Apply が上記 topic IAM を更新できるようにする（New Relic トピックと同一方式。`roles/pubsub.admin` は付与しない）。Deploy SA は自身にこのロールを付与できないため、新規環境では (1) 一度 Apply してトピックを作成（この回は topic IAM リソースが失敗する）→ (2) トピックの `setIamPolicy` 権限を持つ管理者が `gcloud pubsub topics add-iam-policy-binding budget-alert-topic-${environment} --member=serviceAccount:<Deploy SA> --role=projects/<project>/roles/pubsubTopicIamManager` を実行 → (3) 再 Apply、の順で bootstrap する（本番 `sumifu` は 2026-09-28 に実施済み）。
  - `google_monitoring_notification_channel.alert_pubsub` は `monitoring_notification_publisher` に `depends_on` する。


---

## 4. セキュリティ & IAM 設計 (`iam.tf`, `secrets.tf`)
- サービスアカウント: `crawler-runner@${project_id}.iam.gserviceaccount.com`
- 最小権限ロール付与:
  - `roles/cloudsql.client` (Cloud SQL 接続)
  - `roles/storage.objectAdmin` (画像 GCS バケット)
  - `roles/secretmanager.secretAccessor` (秘密情報取得。対象 Secret は `iam.tf` の `secret_accessor` for_each で限定: `db_password` / `slack_bot` / `slack_app` / `new_relic_license_key`)
  - `roles/run.invoker` (Cloud Scheduler からの Job 起動権限)
- **New Relic ライセンスキー**: `secrets.tf` の `realestate-new-relic-license-key-${var.environment}` を Cloud Run が参照するため、必ず `secret_accessor` に含める（Issue #484）。欠落時は `SecretsAccessCheckFailed` となる。
