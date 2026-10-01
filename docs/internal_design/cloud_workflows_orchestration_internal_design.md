# Cloud Workflows パイプライン統合オーケストレーション内部設計書

## 1. ワークフロー定義仕様 (`terraform/workflows/daily_pipeline.yaml`)

```yaml
main:
  params: [args]
  steps:
    - initVars:
        assign:
          - projectId: ${sys.get_env("GOOGLE_CLOUD_PROJECT_ID")}
          - location: "asia-northeast1"
          - zone: "asia-northeast1-b"
          - proxysqlInstance: "proxysql-instance-prod"
          - crawlerJob: "realestate-crawler-pipeline-prod"
          - mlPipelineJob: "realestate-ml-pipeline-prod"
          - crawlTimeoutSec: 18000 # 5時間
    - tryPipeline:
        try:
          steps:
            - startProxySQL:
                call: googleapis.compute.v1.instances.start
                args:
                  project: ${projectId}
                  zone: ${zone}
                  instance: ${proxysqlInstance}
            - waitProxySQL:
                call: sys.sleep
                args:
                  seconds: 30
            - runCrawler:
                call: googleapis.run.v2.projects.locations.jobs.run
                args:
                  name: ${"projects/" + projectId + "/locations/" + location + "/jobs/" + crawlerJob}
                result: crawlerExecution
            - monitorCrawler:
                call: monitorJobExecution
                args:
                  executionName: ${crawlerExecution.name}
                  timeoutSec: ${crawlTimeoutSec}
            - runMLPipeline:
                call: googleapis.run.v2.projects.locations.jobs.run
                args:
                  name: ${"projects/" + projectId + "/locations/" + location + "/jobs/" + mlPipelineJob}
                result: mlExecution
            - waitMLPipeline:
                call: monitorJobExecution
                args:
                  executionName: ${mlExecution.name}
                  timeoutSec: 7200
        retry:
          predicate: ${customRetryPredicate}
          max_retries: 1
        finally:
          steps:
            - stopProxySQL:
                call: googleapis.compute.v1.instances.stop
                args:
                  project: ${projectId}
                  zone: ${zone}
                  instance: ${proxysqlInstance}
```

## 2. クローラー内ハング監視（無進捗検知）の実装

### 監視ループロジック（`run_all_crawlers.py`）
1. 各子プロセス起動時に `last_activity_time[idx] = time.time()` を初期化。
2. 標準出力ハンドラまたは DB レコード更新時に `last_activity_time[idx] = time.time()` を更新。
3. ループ内で `now - last_activity_time[idx] > HANG_THRESHOLD_SEC (300s)` を検知した場合：
   - `os.killpg(pgid, signal.SIGKILL)` を発行。
   - `FailureReporter.record_job_failure(...)` に `error_type="HangSilentFailure"` として記録。
   - Slack に「❌ 【ハング強制終了: 5分間無進捗】」を通知。
   - ジョブを打ち切り、次のキューへ進行。

## 3. 単体・結合テスト観点
1. `test_workflows_terraform.py`:
   - Workflows リソース定義の構文・タイムアウト値（5h / 7h）のアサーション。
2. `test_crawler_hang_watchdog.py`:
   - 5分間沈黙した子プロセスが正しくハング判定され SIGKILL されることのモック検証。
3. `test_workflows_finally_stop.py`:
   - ワークフローの例外発生時にも必ず ProxySQL 停止ステップが通過することの構文的検証。
