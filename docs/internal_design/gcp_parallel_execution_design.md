# GCP 並列分散実行 内部設計書 (Cloud Tasks + Cloud Run Architecture)

## 1. 目的
本設計書は、GCP (Cloud Tasks + Cloud Run) 上で各ポータル・仲介サイトのクローリングをレートリミット保護付きで分散並列実行し、MLパイプラインを高速化するための詳細仕様、データモデル、シーケンス、およびAPI定義を規定する。

---

## 2. アーキテクチャ概要

```mermaid
sequenceDiagram
    autonumber
    participant Sch as Cloud Scheduler
    participant Disp as Dispatcher Job (run_dispatcher.py)
    participant MIG as ProxySQL MIG
    participant CT as Cloud Tasks (crawler-queue)
    participant CR as Cloud Run Workers (/api/crawl/task)
    participant DB as Cloud SQL (ProxySQL経由)
    participant ML as ML Pipeline Job (run_ml_pipeline.py)

    Sch->>Disp: Daily Trigger (01:00 JST)
    Disp->>MIG: Step 0a: ProxySQL MIG 起動 (size: 0 -> 1)
    Disp->>DB: Step 0b: DB Migration
    Disp->>CT: Step 1: Enqueue Crawl Tasks (45 jobs, Smallest-Site-First)
    Note over Disp: Dispatcher 正常終了 (exit 0 / 課金停止)

    par Cloud Tasks Dispatch (Concurrent Workers <= 10, App Pool=None)
        CT->>CR: POST /api/crawl/task (mitsui - mansion)
        CR->>DB: Crawl & Save Records
        CR->>DB: Record Task Status (COMPLETED)
        CR-->>CT: HTTP 200 OK
    and
        CT->>CR: POST /api/crawl/task (sumifu - kodate)
        CR-->>CR: 0件取得 or 相手先エラー検知
        CR->>DB: Record Task Status (FAILED)
        CR-->>CT: HTTP 200 OK (無限リトライ防止・タスク消化)
    end

    Note over ML: クロール全完了後に起動 (Cloud Workflows 等)
    ML->>DB: Barrier Check (未完了・失敗率検査)
    ML->>DB: Step 1.5: Validate & Clean Data
    ML->>DB: Step 2: ML Model Re-Training (n_jobs=-1)
    ML->>DB: Step 3: Bulk ML Evaluation (ThreadPoolExecutor)
    ML->>DB: Step 4: Hot Property Recommendation (Slack)
    ML->>MIG: Step 5: ProxySQL MIG 停止 (size: 1 -> 0)
    Note over ML: ML Pipeline Job 正常終了 (exit 0)
```

---

## 3. Cloud Tasks キュー定義 (Terraform)
- **キュー名**: `crawler-tasks-${var.environment}`
- **レート制御 (`rate_limits`)**:
  - `max_dispatches_per_second`: 5.0（全体ディスパッチ速度）
  - `max_concurrent_dispatches`: 10（同時実行ワーカー上限数）
- **リトライ制御 (`retry_config`)**:
  - `max_attempts`: 2
  - `min_backoff`: "10s"
  - `max_backoff`: "60s"

---

## 4. ワーカーエンドポイント (`/api/crawl/task`)
- **メソッド**: `POST`
- **リクエストボディ**:
  ```json
  {
    "company": "mitsui",
    "property_type": "mansion",
    "execution_date": "2026-09-19"
  }
  ```
- **処理内容**:
  1. `main.py` 内のディスパッチマップから対象関数を特定。
  2. クローラーを実行し、新規保存件数および所要時間を計測。
  3. `CrawlerTaskExecution` モデルへステータス（COMPLETED / FAILED）を記録。
  4. 正常終了時は `{"status": "success", "scraped_count": N}` (HTTP 200)。
  5. 異常終了時は `{"status": "failed", "error": "..."}` (HTTP 500: Cloud Tasks リトライ用)。

---

## 5. タスクディスパッチャー (`package/utils/cloud_tasks_dispatcher.py`)
- `dispatch_all_crawl_jobs(service_url, queue_path, skip_portals=False)`:
  - `CRAWL_JOBS` を走査し、Cloud Tasks API でタスクを作成・投入。
  - 各タスクに OIDC トークン（Crawler Runner Service Account）を付加。
  - ローカル実行時や GCP 外環境では、フォールバックとしてローカル並列実行（従来の `run_all_crawlers.py`）を自動起動。
