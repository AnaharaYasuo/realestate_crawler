# 共有ProxySQL誤認停止防止および全DB接続有限タイムアウト強制 基本設計書 (Issue #916)

## 1. システム構成と責務

### 1.1 エージェント運用ルール (\`.agents/AGENTS.md\`)
- ユーザー指示「止めておいて」等に対する解釈スコープの明確化：
  - **許可**: ローカルコンテナ停止、ローカルプロセス停止、IAPトンネル終了、対象個別 Cloud Run 実行のキャンセル (\`gcloud run jobs executions cancel\`)。
  - **禁止**: 共有 ProxySQL VM (\`proxysql-instance-prod\`) や Cloud SQL に対する \`gcloud compute instances stop\` 等の直接発行。

### 1.2 共通DB設定 (\`realestateSettings.py\`)
- Django DB 設定のファクトリ・初期化処理において、\`package.utils.db_timeouts.bound_mysql_timeouts\` を自動呼び出し。
- すべての Django DB 接続 OPTIONS に以下が確実に設定される：
  - \`charset: utf8mb4\`
  - \`connect_timeout: 10\`
  - \`read_timeout: 120\`
  - \`write_timeout: 120\`

### 1.3 パイプライン停止ガード (\`run_pipeline.py\`)
- \`_can_stop_shared_proxysql()\` の判定ロジック強化：
  1. \`_task_count > 1\`: 同一実行内の他タスク状態（\`CrawlerTaskExecution\`）がすべて終端か確認。
  2. \`_task_count <= 1\` または上記クリア後:
     - 共有 GCP リソース環境 (\`IS_CLOUD\`) において、他にアクティブな Cloud Run 実行 (\`realestate-crawler-pipeline\`, \`realestate-ml-pipeline\`) が存在するかをチェック（自 execution_id を除く）。
     - 他にアクティブな実行が 1 件でもあれば、ProxySQL の停止をスキップし、ログ出力の上 Safety-Net へ委譲する。
