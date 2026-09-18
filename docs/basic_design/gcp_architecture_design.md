# GCP アーキテクチャ基本設計書 (GCP Architecture Basic Design)

## 1. 全体構成概要
本システムは、完全マネージドなサーバーレス実行基盤（Cloud Run Jobs + Cloud Scheduler）を中心に、データベース（Cloud SQL for MySQL）、ストレージ（Cloud Storage）、およびセキュリティ基盤（VPC + Cloud NAT + Secret Manager）で構成される。

```mermaid
flowchart TB
    subgraph Scheduling ["スケジューリング"]
        CS[Cloud Scheduler\n01:00 JST / 16:00 UTC]
    end

    subgraph Security ["認証・秘密情報"]
        SM[Secret Manager\nDB接続情報・Slack Token]
        IAM[Service Account\n最小権限ロール]
    end

    subgraph Compute ["コンピュート (Serverless)"]
        CRJ["Cloud Run Jobs\n(Crawler & ML Pipeline)\nPlaywright / tmpfs / 4GB RAM"]
        CRS["Cloud Run Service\n(Slack Agent Host)"]
    end

    subgraph Network ["VPC Network (閉域網)"]
        SVA[Serverless VPC Access\nConnector]
        CR[Cloud Router]
        NAT["Cloud NAT\n(Static External IP)"]
    end

    subgraph DataStore ["マネージド永続化層"]
        CSQL[("Cloud SQL (MySQL 8.0)\nPrivate IP 接続")]
        GCS[("Cloud Storage (GCS)\n物件画像バケット")]
    end

    subgraph External ["外部サービス / インターネット"]
        SITES[不動産ポータル・仲介各社\nHomes / Athome / 三井 / 住友 etc.]
        SLACK[Slack API / チャンネル]
    end

    CS -->|Trigger| CRJ
    CRJ -->|Read Secrets| SM
    CRJ -->|Egress Route| SVA
    CRS -->|Read Secrets| SM

    SVA -->|Private Connection| CSQL
    SVA -->|Route to Internet| CR
    CR --> NAT
    NAT -->|Fixed IP Access| SITES

    CRJ -->|Store Images| GCS
    CRJ -->|Alert / Recommend| SLACK
    CRS -->|Socket / Webhook| SLACK
```

---

## 2. コンポーネント詳細設計

| コンポーネント | GCPサービス | 仕様・サイジング | 役割・選定根拠 |
|---|---|---|---|
| **バッチ実行基盤** | Cloud Run Jobs | 2 vCPU, 4 GiB RAM, タイムアウト 24h, tmpfs 有効 | 初回DBスキーマ自動反映、クローラーおよびML一括評価を実行。Playwrightのメモリ枯渇を防止し、非稼働時コスト¥0。 |
| **定期トリガー** | Cloud Scheduler | 毎日 16:00 UTC (01:00 JST) 実行 | Cloud Run Jobs の実行 API を OIDC 認証付きで安全にキック。 |
| **リレーショナルDB** | Cloud SQL for MySQL 8.0 | `db-f1-micro` または `db-g1-small`, SSD 20GB (自動拡張) | 物件マスタ、トランザクション、地価、評価データの格納。自動バックアップ対応。 |
| **オブジェクトストレージ** | Cloud Storage (GCS) | Standard クラス, リージョン: `asia-northeast1` | 物件画像、エビデンス、モデルアーティファクト保存。MinIOからの完全代替。 |
| **コンテナレジストリ** | Artifact Registry | Docker リポジトリ (`asia-northeast1`) | クローラーDockerイメージの保存・バージョン管理。 |
| **送信元IP固定** | Serverless VPC Access + Cloud NAT | e2-micro コネクタ (2~10台), 手動静的外部IP 1本 | クロール先ポータルからのBot検知・IPブロックを回避。 |
| **シークレット管理** | Secret Manager | レプリケーション: 自動 | DBパスワード、Slack Bot Token、Slack App Token を安全に注入。 |
| **実行権限** | IAM Service Account | クローラー専用 SA | Cloud SQL クライアント、Storage オブジェクト管理者、Secret アクセサーを付与。 |
| **予算・請求アラート** | Cloud Billing Budget + Cloud Monitoring | しきい値: 50%, 80%, 100%, 120%(予測) | メール及びPub/Sub通知により、リソース暴走や過大請求を即時防止。 |


---

## 3. 分散並列実行アーキテクチャ（Cloud Tasks + Cloud Run ワーカー ＆ レートリミット制御）

### 3.1 Cloud Tasks によるクローラー分散並列化 & 流量制御
Cloud Tasks のキューイングおよび流量制御機能（`max_dispatches_per_second = 5`, `max_concurrent_dispatches = 10` 等）を活用し、全 45 以上の巡回ジョブ（サイト×種別）を Cloud Run サービスへディスパッチして同時分散実行する。

- **レート制御 & BAN防止**:
  - 同一ドメインへの過度な同時リクエストをキューのレートリミット（1〜2 req/sec）で抑制し、IP BAN を確実に防止しながら、異ドメイン間（三井・住友・東急・ポータル等）は最大 10〜20 並列で同時クローリング。
- **タスクディスパッチ (`dispatch_cloud_tasks.py`)**:
  - スケジューラー起動時に Smallest-Site-First 順でタスクをエンキュー。OIDC 認証付きで Cloud Run のエンドポイント（`/api/crawl/task`）を呼び出し。
- **完了検知 & 後続パイプライン連携**:
  - 各 Cloud Run ワーカーは担当ジョブ完了時に DB（`crawler_task_execution`）へステータスを更新。
  - ディスパッチャーまたは Coordinator が全ジョブの完了を検知後、後続ステップ（バリデーション ➔ ML再学習 ➔ バルク推論 ➔ Slack通知）を一括実行。

### 3.2 MLモデル学習・バルク推論の並列最適化
- **MLモデル学習 (`train.py`)**:
  - LightGBM, XGBoost, CatBoost, RandomForest の学習時に `n_jobs=-1`（または利用可能CPUコア数）を指定し、マルチコア並列化。
- **バルク推論 (`run_bulk_ml_evaluation.py`)**:
  - `ThreadPoolExecutor`（4〜8並行）により、物件モデル群を並行して一括推論＆DB永続化。直列ループによる処理ボトルネックを解消。
- **サイト内詳細取得並行度 (`_getCloudPararellLimit`)**:
  - 環境変数 `CLOUD_DETAIL_CONCURRENCY`（デフォルト 5）により、GCP帯域に最適化された並行リクエスト数を安全に設定可能。


