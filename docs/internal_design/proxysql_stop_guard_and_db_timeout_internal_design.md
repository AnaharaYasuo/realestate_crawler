# 共有ProxySQL誤認停止防止および全DB接続有限タイムアウト強制 内部設計書 (Issue #916)

## 1. モジュール詳細設計

### 1.1 \`.agents/AGENTS.md\`
新セクション「共有インフラ直接停止厳禁原則（Cloud Run直接停止は許可）」を追加：
- 曖昧な停止指示（「止めて」「中断して」等）を受けた際、エージェントはローカル環境（Docker / Python / IAPトンネル）または該当する個別 Cloud Run 実行（\`gcloud run jobs executions cancel\`）のみを停止対象とすること。
- 共有インフラリソース（ProxySQL VM、Cloud SQL等）を直接 \`gcloud compute instances stop\` 等で停止してはならない。

### 1.2 \`src/crawler/realestateSettings.py\`
- モジュール冒頭で \`from package.utils.db_timeouts import bound_mysql_timeouts\` をインポート。
- \`get_database_config()\` 内で返却辞書に対して \`bound_mysql_timeouts(config)\` を実行。
- \`configure()\` 内で本番用 MySQL 設定辞書に対して \`bound_mysql_timeouts(settings_dict)\` を実行。

### 1.3 \`src/crawler/package/utils/gcp_resources.py\`
- \`has_active_other_cloud_run_executions(project_id: str | None = None, region: str | None = None, current_execution_id: str | None = None) -> bool\` ヘルパー関数を新設。
- \`run_v2\` または REST API で \`realestate-crawler-pipeline\` および \`realestate-ml-pipeline\` の executions を照会。
- \`completionTime\` または Completed 状態がなく、かつ \`name\` が \`current_execution_id\` と異なるアクティブな実行が存在する場合に \`True\` を返す。API エラー時は安全側に倒して \`True\`（停止不可・Safety-Net委譲）を返す。

### 1.4 \`src/crawler/scripts/ops/run_pipeline.py\`
- \`_can_stop_shared_proxysql()\` を更新：
  - \`_task_count <= 1\` で即 \`True\` を返すのではなく、\`has_active_other_cloud_run_executions(current_execution_id=get_execution_id())\` を評価。
  - 他の実行が存在する場合は \`logger.warning("⚠️ [Teardown Guard] 他の Cloud Run 実行が稼働中のため共有 ProxySQL 停止をスキップし Safety-Net に委譲します")\` を出力して \`False\` を返す。
