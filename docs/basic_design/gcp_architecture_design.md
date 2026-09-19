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
        ILB["Internal Load Balancer (ILB)\nTCP: 6033"]
        CR[Cloud Router]
        NAT["Cloud NAT\n(Static External IP)"]
    end

    subgraph ProxyLayer ["コネクションプーリング層"]
        MIG["ProxySQL MIG (e2-micro x 2)\nMulti-Zone / Auto-healing"]
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

    SVA -->|MySQL: 6033| ILB
    ILB -->|TCP Load Balancing| MIG
    MIG -->|Multiplexed DB Conns| CSQL
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
| **コネクションプール** | Compute Engine MIG | `e2-micro` 1〜2台 (Autoscaler: Min 1, Max 2, Multi-Zone), Debian 12, ProxySQL | 多数のクローラープロセスからの同時DB接続を集約・多重化。CPU負荷に応じた動的スケールとCloud SQL接続上限（計100）の保護。 |
| **内部負荷分散** | 内部TCPロードバランサー (ILB) | リージョン内部ロードバランサー, ポート 6033, TCPヘルスチェック, コネクションドレイン (300秒) | ProxySQL MIG へのトラフィック分散、障害時自動フェイルオーバー、スケールイン時のクエリ保護。 |
| **リレーショナルDB** | Cloud SQL for MySQL 8.0 | `db-f1-micro` または `db-g1-small`, SSD 20GB (自動拡張) | 物件マスタ、トランザクション、地価、評価データの格納。自動バックアップ対応。 |
| **オブジェクトストレージ** | Cloud Storage (GCS) | Standard クラス, リージョン: `asia-northeast1` | 物件画像、エビデンス、モデルアーティファクト保存。MinIOからの完全代替。 |
| **コンテナレジストリ** | Artifact Registry | Docker リポジトリ (`asia-northeast1`) | クローラーDockerイメージの保存・バージョン管理。 |
| **送信元IP固定** | Serverless VPC Access + Cloud NAT | e2-micro コネクタ (2~10台), 手動静的外部IP 1本 | クロール先ポータルからのBot検知・IPブロックを回避。 |
| **シークレット管理** | Secret Manager | レプリケーション: 自動 | DBパスワード、Slack Bot Token、Slack App Token を安全に注入。 |
| **実行権限** | IAM Service Account | クローラー専用 SA / ProxySQL専用 SA | Cloud SQL クライアント、Storage オブジェクト管理者、Secret アクセサー等を最小権限で付与。 |
| **予算・請求アラート** | Cloud Billing Budget + Cloud Monitoring | しきい値: 50%, 80%, 100%, 120%(予測) | メール及びPub/Sub通知により、リソース暴走や過大請求を即時防止。 |


---

## 3. 分散並列実行アーキテクチャ（Cloud Tasks + Cloud Run ワーカー ＆ レートリミット制御）

### 3.1 Cloud Tasks によるクローラー分散並列化 & 流量制御
Cloud Tasks のキューイングおよび流量制御機能（`max_dispatches_per_second = 5`, `max_concurrent_dispatches = 10` 等）を活用し、全 45 以上の巡回ジョブ（サイト×種別）を Cloud Run サービスへディスパッチして同時分散実行する。

- **レート制御 & サイト規模別並行プロセス制御**:
  - 全20〜25社に対して一斉にジョブを開始し、会社間の並列度を最大化。
  - 同一ドメインへの過度な負荷・BANを防止しつつ処理能力を最適化するため、取扱件数・ブラウザ負荷に応じて会社ごとの同時プロセス数を階層制御：
    - **Homes (超大規模ポータル HTTP)**: 同時 **5 プロセス**
    - **Athome (超大規模ポータル Playwright)**: 同時 **3 プロセス** (並行処理加速)
    - **大手5社 (三井, 住友, 東急, 野村, ミサワ)**: 同時 **2 プロセス**
    - **中小・電鉄・ハウスメーカー (17社)**: 同時 **1 プロセス** (同一会社内完全直列)
- **タスクディスパッチ (`dispatch_cloud_tasks.py` / `run_all_crawlers.py`)**:
  - スケジューラー起動時に各社から1種別ずつ全社一斉に投入。同一会社内は割り当て上限枠内で順次直列に消化。
- **完了検知 & 後続パイプライン連携**:
  - 各ワーカーは担当ジョブ完了時に DB（`crawler_task_execution`）へステータスを更新。
  - ディスパッチャーまたは Coordinator が全ジョブの完了を検知後、後続ステップ（バリデーション ➔ ML再学習 ➔ バルク推論 ➔ Slack通知）を一括実行。

### 3.2 MLモデル学習・バルク推論の並列最適化
- **MLモデル学習 (`train.py`)**:
  - LightGBM, XGBoost, CatBoost, RandomForest の学習時に `n_jobs=-1`（または利用可能CPUコア数）を指定し、マルチコア並列化。
- **バルク推論 (`run_bulk_ml_evaluation.py`)**:
  - `ThreadPoolExecutor`（4〜8並行）により、物件モデル群を並行して一括推論＆DB永続化。直列ループによる処理ボトルネックを解消。
- **サイト内詳細取得並行度 (`_getCloudPararellLimit`)**:
  - 環境変数 `CLOUD_DETAIL_CONCURRENCY`（デフォルト 5）により、GCP帯域に最適化された並行リクエスト数を安全に設定可能。


