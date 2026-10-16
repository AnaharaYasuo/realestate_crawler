# 外部設計書: Issue #952 クローラー子プロセスからの処理件数直接回収およびステップ間DB接続回復

## 1. システム構成・フロー変更点

### 変更前フロー
```mermaid
sequenceDiagram
    participant Orchestrator as run_all_crawlers.py
    participant Subprocess as main.py (子プロセス)
    participant DB as ProxySQL / Cloud SQL

    Orchestrator->>Subprocess: subprocess.Popen(main.py)
    Subprocess->>DB: INSERT / UPDATE 物件
    Subprocess-->>Orchestrator: exit(0)
    Orchestrator->>DB: COUNT(*) WHERE inputDateTime >= today (get_count_for_job)
    Note over Orchestrator,DB: 大量同時発行でProxySQL飽和、タイムアウト (9001/2013)
    Orchestrator->>Orchestrator: Job Failure と誤判定してSlack発報
```

### 変更後フロー
```mermaid
sequenceDiagram
    participant Orchestrator as run_all_crawlers.py
    participant Subprocess as main.py (子プロセス)
    participant MetricsFile as logs/runs/<today>/metrics_<company>_<ptype>.json
    participant DB as ProxySQL / Cloud SQL

    Orchestrator->>Subprocess: subprocess.Popen(main.py)
    Subprocess->>DB: INSERT / UPDATE 物件
    Subprocess->>MetricsFile: 処理件数書き出し (detail_cnt, skipped_cnt)
    Subprocess-->>Orchestrator: exit(0)
    Orchestrator->>MetricsFile: メトリクス直接読み込み
    alt メトリクス取得成功
        Orchestrator->>Orchestrator: DBクエリ発行せず成功処理 (COUNT(*) ゼロ)
    else ファイル未検出 (フォールバック)
        Orchestrator->>DB: COUNT(*) (get_count_for_job)
        Note over Orchestrator: 仮にDBエラーになっても exit_code==0 なら成功扱い
    end
```

## 2. インターフェース設計

### 2.1 メトリクスファイル形式
- パス: `logs/runs/<YYYYMMDD>/metrics_<company>_<property_type>.json`
- フォーマット:
```json
{
  "company": "rearie",
  "property_type": "kodate",
  "detail_cnt": 42,
  "skipped_cnt": 5,
  "total_fetched": 47,
  "timestamp": "2026-10-16T22:30:00.000000"
}
```

### 2.2 Orchestrator (`run_all_crawlers.py`) 側ハンドリング
- 子プロセスの完了監視時、メトリクスファイルが存在するかを判定。
- 存在する場合: `count = metrics["detail_cnt"]` を取得し、DBアクセスを一切スキップ。
- 存在しない場合: 既存の `get_count_for_job()` を呼ぶが、エラーハンドリング内で `exit_code == 0` の場合はジョブステータスを `SUCCESS`（または `WARNING`）とし、`FAIL` にはしない。
