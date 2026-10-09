# タスクアレイ完了時のプロセス即時終了保証および最終タスクへの全体集約委譲 内部設計書 (Issue #823)

## 1. 改修対象コンポーネント

1. `src/crawler/scripts/ops/run_all_crawlers.py`:
   - クローラーのバッチ実行メインスクリプト。
   - 自タスクジョブ完了後の集約判定ロジック関数 `should_perform_final_aggregation(task_index, task_count)` を新設。
   - `task_count > 1` の場合、自タスクの `CrawlerTaskExecution` を更新後に他タスクの状態を確認。
   - 他タスクに未完了タスクがある場合は即座に関数を return（または `sys.exit(0)`）。
   - 最後のタスクのみ `db_summary`、Slack レポート送信、`monitor_error_pages.py` を実行。

2. `src/crawler/scripts/ops/run_pipeline.py`:
   - パイプライン制御スクリプト。
   - `_run_crawler_step` で `is_task_array` の場合、`run_all_crawlers.py` 完了後に `sys.exit(0)` または `sys.exit(1)` でプロセスを確実に即時終了させる（`return` 後の非デーモン待機を防止）。

## 2. 詳細設計ロジック

### 2.1 最終タスク判定関数 `is_last_completing_task()`
```python
def is_last_completing_task(task_index: int | None, task_count: int) -> bool:
    """タスクアレイ実行において、自タスク以外の全タスクが終端状態 (COMPLETED/FAILED) かを判定する"""
    if task_count <= 1 or task_index is None:
        return True
    
    execution_id = get_execution_id()
    execution_date = get_execution_date()
    if not execution_id:
        # 実行 ID 不明の場合は安全のため単独扱い（集計実行）
        return True
        
    try:
        from django.db import close_old_connections
        close_old_connections()
        records = list(CrawlerTaskExecution.objects.filter(
            execution_date=execution_date,
            execution_id=execution_id
        ))
        status_map = {r.task_index: r.status for r in records}
        pending = [
            idx for idx in range(task_count)
            if idx != task_index and status_map.get(idx) not in ("COMPLETED", "FAILED")
        ]
        return len(pending) == 0
    except Exception as e:
        logger.warning(f"Failed to check other tasks status: {e}. Defaulting to not last task.")
        return False
```

### 2.2 終了シーケンスフロー
```
run_all_crawlers.py:
  1. while job_queue or active_processes:
       ... 全ジョブ消化 ...
  2. summary 作成 & JSON 出力
  3. if task_exec_record:
       task_exec_record.status = "COMPLETED" / "FAILED"
       task_exec_record.save()
  4. if task_count > 1 and not is_last_completing_task(task_index, task_count):
       logger.info(f"Task {task_index}/{task_count} finished. Other tasks still running. Skipping aggregation and exiting immediately.")
       return
  5. --- ここから下は「単体タスク」または「最終完了タスク」のみ実行 ---
     db_summary 集計
     Slack 総合レポート送信
     monitor_error_pages.py キック
```

### 2.3 `run_pipeline.py` の確実なプロセス終了
`run_pipeline.py` において、`_run_crawler_step` が完了した後の Worker 終了処理：
```python
if is_task_array:
    logger.info(
        f"✔ [{'Coordinator' if is_coordinator else 'Worker'}] Task {task_index}/{task_count} のクローリングが完了しました。"
        "集約レポート・学習・価格推定は ML Pipeline Job が実行します。コンテナを終了します。"
    )
    if not crawler_ok:
        sys.exit(1)
    # 明示的な sys.exit(0) でプロセスを直ちにクリーンアップ
    sys.exit(0)
```
これにより、親プロセスが不要な待機やスレッド終了待ちでハングすることなく即座に `exit(0)` し、Cloud Run コンテナが破棄される。

## 3. テスト計画
- `test_is_last_completing_task`:
  - `task_count=1` ➔ 常に True
  - `task_count=5`, 他がすべて COMPLETED ➔ True
  - `task_count=5`, 他に RUNNING あり ➔ False
  - DB エラー時 ➔ False
- `test_task_array_fast_exit`:
  - 先行タスク実行時、`db_summary` や `monitor_error_pages.py` が呼び出されずに早期リターンすること。
  - 最終タスク実行時、全体集約処理が実行されること。
