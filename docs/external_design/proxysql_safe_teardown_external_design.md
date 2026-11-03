# ProxySQL停止安全ガード化と並列実行巻き込み停止防止 外部設計書 (Issue #1216)

## 1. システム全体シーケンス

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 開発者 (ローカル本番実行)
    participant WF as Cloud Workflows
    participant ML as Cloud Run (ML Pipeline)
    participant Guard as _can_stop_shared_proxysql
    participant GCE as GCE (proxysql-instance-prod)
    participant SN as Safety-Net (ensure_resources_stopped.py)

    Note over Dev, GCE: Devがローカル本番実行を開始 (ProxySQL経由でCloud SQL書き込み)
    WF->>GCE: startProxySQL (インスタンス起動)
    WF->>ML: run_ml_pipeline.py 実行
    Note over ML: ML処理実行中 (または例外発生)
    ML->>Guard: _can_stop_shared_proxysql() 呼び出し
    Guard->>Guard: IS_CLOUD環境か確認
    Guard->>Guard: has_active_other_cloud_run_executions() 確認
    alt 他ジョブ稼働中 or ローカル実行
        Guard-->>ML: False (停止不可・スキップ)
        ML->>ML: 停止をスキップしログ出力
    else 単独実行・他ジョブ無し
        Guard-->>ML: True (停止許可)
        ML->>GCE: scale_proxysql_mig(target_size=0)
    end
    WF->>WF: Workflows 終了 (Workflows自身は停止を叩かない)
    Note over Dev: Devのローカル実行は安全に継続
    Note over Dev: Devのローカル実行完了
    Note over SN, GCE: 毎時0分 Safety-Netがトラフィック監視の上で停止
```

## 2. 外部インターフェース仕様

### 2.1 `run_ml_pipeline.py`
- 環境変数 `IS_CLOUD` が未設定の場合：
  - ProxySQL の停止は実行されず、「ローカル環境での実行のため ProxySQL 停止をスキップします」とログ出力して終了する。
- 環境変数 `IS_CLOUD=true` の場合：
  - Cloud Run API で他実行を確認。未完了の別実行がある場合は停止をスキップし、「他ジョブ実行中のため ProxySQL 停止をスキップし Safety-Net に委譲します」とログ出力。
  - 単独実行の場合は正常に `scale_proxysql_mig(target_size=0)` を発行して終了。

### 2.2 Cloud Workflows
- `daily_pipeline.yaml`:
  - `startProxySQL` は継続（ジョブ開始時の起動責務は保持）。
  - パイプライン終了時（`stopProxySQLOnSuccess`）およびエラー時（`stopProxySQLOnError`）の即時停止ステップを撤廃。
  - ジョブ内部の Teardown および毎時 0 分の Safety-Net に停止責務を委譲。
- `recrawl_anomalies_pipeline.yaml`:
  - 同様に即時停止ステップを撤廃。
