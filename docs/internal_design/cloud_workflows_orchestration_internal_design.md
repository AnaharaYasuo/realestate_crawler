# Cloud Workflows パイプライン統合オーケストレーション内部設計書

## 1. ワークフロー定義仕様 (`terraform/workflows/daily_pipeline.yaml`)

```yaml
main:
  params: [args]
  steps:
    - initVars:
        assign:
          - pipelineStart: ${sys.now()}
          - crawlerFailed: false
          - crawlerError: null
          ...
    - tryPipeline:
        try:
          steps:
            - startProxySQL: ...
            - waitProxySQLReady: ...
            - runCrawlerTasks: ...
            - waitCrawlerCompletion:
                try:
                  call: monitorJobExecution
                  args:
                    executionName: ${crawlerExecutionName}
                    timeoutSec: ${crawlTimeoutSec}
                except:
                  as: crawlErr
                  steps:
                    - recordCrawlError:
                        assign:
                          - crawlerFailed: true
                          - crawlerError: ${crawlErr}
            - calculateRemainingTime: ...
            - checkMLDeadline: ...
            - runMLAndEstimation: ...
            - waitMLCompletion:
                call: monitorJobExecution
                ...
        except:
          as: pipelineError
          steps:
            - stopProxySQLOnError: ...
            - rethrowPipelineError:
                raise: ${pipelineError}
    - stopProxySQLOnSuccess: ...
    - checkFinalStatus:
        switch:
          - condition: ${crawlerFailed}
            raise:
              error: "CrawlerPhaseFailed"
              message: '${"Crawler phase had errors: " + string(crawlerError)}'
```

### 1.1 monitorJobExecution における子ジョブ消失検知（Fast-Fail）
子ジョブ（Cloud Run Job Execution）が強制終了・手動キャンセル・リソース削除等により Cloud Run 上から消失（404 Not Found または API 取得エラー）した場合、従来の無限リトライループを排除し、有限試行（連続 3 回）で高速失敗させる：
- `consecutiveGetErrors` カウンタ（初期値 0）
- `executions.get` 成功時: `consecutiveGetErrors = 0` にリセット
- `executions.get` 例外発生時: `consecutiveGetErrors = consecutiveGetErrors + 1`
  - `consecutiveGetErrors >= 3` の場合: 直ちに `raise: {error: "JobExecutionNotFound", message: "Cloud Run Job execution vanished or failed to fetch after 3 attempts"}`
  - `consecutiveGetErrors < 3` の場合: 10秒待機後に再試行
- `JobExecutionNotFound` は親の `tryPipeline` の `except: as: pipelineError` で捕捉され、`stopProxySQLOnError` を確実に通過してリソース解放を保証。

### 1.2 死活検証（URL verification）のパラメータ制御とデフォルトスキップ
- `daily_pipeline.yaml` の引数に `skipUrlCheck`（デフォルト `true`）を追加。
- ワークフロー呼び出し側（引数未指定時および Cloud Scheduler 日次実行）ではデフォルトで `skipUrlCheck: true` となり、Crawler Job および ML Pipeline Job に `--skip-url-check` を自動付与。
- 手動実行時（`{"skipUrlCheck": false}` または `{"enableUrlCheck": true}`）のみ `--skip-url-check` の付与をスキップし、Step 2（`validate_data.py`）で約24分の全件URL死活確認を実行。
- `run_pipeline.py`（Crawler Job）に `--skip-url-check` CLI 引数を追加し、単一タスク/Coordinator 実行時の `_run_post_crawl_pipeline` 経由で `validate_data.py` へオプションを伝搬。

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
3. `test_workflows_finally_stop.py` / `test_workflows_orchestration_568.py`:
   - ワークフローの例外発生時にも必ず ProxySQL 停止ステップが通過することの構文的検証。
   - `monitorJobExecution` に `JobExecutionNotFound` による連続エラー制限と Fast-Fail ロジックが存在することの検証。
