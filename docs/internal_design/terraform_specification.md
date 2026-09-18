# Terraform インフラストラクチャ詳細設計書 (Terraform Internal Specification)

## 1. 構成概要
本設計書は、GCPリソース群を宣言的に管理する Terraform コードのファイル構成、変数仕様、出力仕様、リソース依存関係を定義する。

### 1.1 ディレクトリ構成 (`terraform/`)
```
terraform/
├── main.tf                    # プロバイダー定義 (google, google-beta), バージョン固定, backend設定
├── variables.tf               # 入力変数定義 (型, デフォルト値, 説明)
├── outputs.tf                 # 出力値 (Job名, DB Private IP, GCSバケット名, NAT固定IP)
├── terraform.tfvars.example   # 設定パラメータの雛形
├── network.tf                 # VPC, サブネット, Serverless VPC Access, Cloud Router, Cloud NAT
├── storage.tf                 # Cloud Storage (物件画像・エビデンス)
├── database.tf                # Cloud SQL for MySQL 8.0, ユーザー, データベース
├── secrets.tf                 # Secret Manager (DB接続情報, Slackトークン)
├── artifact_registry.tf       # Artifact Registry Docker リポジトリ
├── iam.tf                     # 実行用 Service Account, IAM Role バインディング
├── cloud_run_job.tf           # Cloud Run Jobs (クローラーバッチ定義, リソース割当, tmpfs)
├── cloud_run_service.tf       # Cloud Run Service (Slack Agent 常時受付)
├── scheduler.tf               # Cloud Scheduler (日次定期キック)
└── budget.tf                  # Cloud Billing 予算アラート (50%, 80%, 100%, 120%予測)
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
| `crawler_timeout` | `string` | `"86400s"` | Cloud Run Jobs タイムアウト（最大24時間） |
| `schedule_cron` | `string` | `"0 16 * * *"` | Cloud Scheduler 実行cron式（UTC 16:00 = JST 01:00） |

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
  - バックアップ設定: 有効（毎日自動バックアップ）

### 3.3 コンピュート (`cloud_run_job.tf`, `cloud_run_service.tf`)
- `google_cloud_run_v2_job`:
  - 実行イメージ: `${region}-docker.pkg.dev/${project_id}/realestate-crawler/crawler:latest`
  - 実行引数: `["python", "src/crawler/scripts/ops/run_pipeline.py"]`
  - 共有メモリ設定: in-memory `emptyDir` ボリュームを `/dev/shm` にマウント（Playwright クラッシュ防止）
  - VPC コネクタ接続: `vpc_access.egress = ALL_TRAFFIC` (全外部通信を Cloud NAT 経由にして固定IP化)
  - 環境変数: Secret Manager からシークレット参照（`value_source`）、Slack 通知先チャンネル ID 設定 (`SLACK_CHANNEL_ID`, `SLACK_DEV_CHANNEL`, `SLACK_ALERT_PROPERTY_ALERT`, `SLACK_RECOMMEND_*`)

---

## 4. セキュリティ & IAM 設計 (`iam.tf`, `secrets.tf`)
- サービスアカウント: `crawler-runner@${project_id}.iam.gserviceaccount.com`
- 最小権限ロール付与:
  - `roles/cloudsql.client` (Cloud SQL 接続)
  - `roles/storage.objectAdmin` (画像 GCS バケット)
  - `roles/secretmanager.secretAccessor` (秘密情報取得)
  - `roles/run.invoker` (Cloud Scheduler からの Job 起動権限)
