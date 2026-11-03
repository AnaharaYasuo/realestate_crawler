# ProxySQL停止安全ガード化と並列実行巻き込み停止防止 要件定義書 (Issue #1216)

## 1. 背景と課題
ローカル環境で本番実行（`run_pipeline.py`、`EXECUTION_ENV=host`）を行っている最中、または複数のジョブが並列で Cloud SQL（ProxySQL経由）に接続している状況において、以下の問題により ProxySQL（`proxysql-instance-prod`）が不意にシャットダウンされ、他ジョブが `OperationalError: 2002 / 2013` で巻き添え切断される障害が発生した。

1. **`run_ml_pipeline.py` のノーガード停止**:
   - `finally` 句において、他ジョブ（クローラーなど）の稼働状況や実行環境（クラウドかローカルか）を一切確認せず、無条件で `scale_proxysql_mig(target_size=0)` を発行している。
2. **Cloud Workflows の直撃停止**:
   - `daily_pipeline.yaml` および `recrawl_anomalies_pipeline.yaml` において、パイプラインの正常完了時および例外発生時（`except` 句）に `googleapis.compute.v1.instances.stop` を無条件で呼び出しており、並列実行中のローカル実行等を巻き添えシャットダウンする。

## 2. 目的
1. ジョブ並列実行時（ローカル本番実行とクラウドジョブの重複、複数クローラー・MLパイプラインの同時実行時）に ProxySQL が誤って強制終了される事故を 100% 防止する。
2. ProxySQL の停止責務を整理し、他のジョブが稼働中である場合は停止を安全にスキップし、毎時 0 分の Safety-Net（`ensure_resources_stopped.py`）に委譲する。

## 3. 要件
### 要件 1: `run_ml_pipeline.py` の Teardown 安全ガード
- `run_ml_pipeline.py` の `finally` 句での停止前に安全判定関数 `_can_stop_shared_proxysql()` を実行すること。
- 判定条件：
  - 非クラウド環境（`IS_CLOUD` なし、またはローカル環境）での実行時は、ProxySQL 停止をスキップすること。
  - クラウド環境であっても、自ジョブ以外の Cloud Run 実行（クローラー、他MLジョブ等）が稼働中（`has_active_other_cloud_run_executions` が `True`）の場合は停止をスキップし、Safety-Net に委譲すること。
  - テスト環境（`dry_run=True`）では安全にシミュレーションできること。

### 要件 2: Cloud Workflows からの無条件停止の撤廃・Safety-Net 委譲
- `daily_pipeline.yaml` および `recrawl_anomalies_pipeline.yaml` から、`stopProxySQLOnSuccess` および `stopProxySQLOnError` による GCE インスタンス直接停止ステップを撤廃する。
- ワークフロー終了時の停止判断は、末尾のジョブ（`run_ml_pipeline.py` や `run_recrawl_anomalies.py` 等）の自律安全ガード、または定期監視の Safety-Net（`ensure_resources_stopped.py`）に委譲する。

### 要件 3: 既存テストおよびアーキテクチャハーネスへの適合
- 既存の Workflows 構文テスト（`test_workflows_orchestration_568.py` 等）を改修仕様に合わせて更新する。
- `run_ml_pipeline.py` の安全ガードを検証するユニットテストを追加する。
