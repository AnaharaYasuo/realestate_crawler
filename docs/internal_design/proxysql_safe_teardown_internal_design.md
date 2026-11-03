# ProxySQL停止安全ガード化と並列実行巻き込み停止防止 内部設計書 (Issue #1216)

## 1. モジュール設計

### 1.1 `src/crawler/scripts/ops/run_ml_pipeline.py`
以下の安全判定ロジック `_can_stop_shared_proxysql()` を実装する。

```python
def _can_stop_shared_proxysql() -> bool:
    """他タスク・他Cloud Run実行が全て終端状態の場合のみ共有 ProxySQL を停止できる (未確定時は Safety-Net に委譲)"""
    if not os.environ.get("IS_CLOUD"):
        logger.info(
            "ℹ️ [Teardown Guard] 非クラウド (ローカル) 環境での実行のため、共有 ProxySQL 停止をスキップします"
        )
        return False

    if has_active_other_cloud_run_executions(
        current_execution_id=get_execution_id()
    ):
        logger.warning(
            "⚠️ [Teardown Guard] 他の Cloud Run 実行が稼働中のため共有 ProxySQL 停止をスキップし Safety-Net に委譲します"
        )
        return False

    return True
```

`finally` 句の改修：
```python
    finally:
        try:
            if _can_stop_shared_proxysql():
                logger.info("Executing teardown hook: stopping ProxySQL MIG (size: 1 -> 0)...")
                scale_proxysql_mig(target_size=0, dry_run=args.dry_run)
            else:
                logger.info("Skipping teardown hook for ProxySQL MIG: safe guard active or delegated to Safety-Net")
        except Exception:
            logger.exception("Failed to scale in ProxySQL MIG in finally block")
```

### 1.2 `terraform/workflows/daily_pipeline.yaml` & `recrawl_anomalies_pipeline.yaml`
- `tryPipeline` 内の `except` から `stopProxySQLOnError` を削除し、エラー時はそのまま `rethrowPipelineError` を実行。
- `tryPipeline` 直後の `stopProxySQLOnSuccess` ステップを削除。
- 代わりに、ProxySQL 停止をパイプライン完了後のジョブ安全ガードおよび Safety-Net へ委譲するコメントを明記。

### 1.3 テストコード設計
- `src/crawler/tests/unit/test_ml_pipeline_proxysql_guard_1216.py`:
  - `IS_CLOUD` がない場合、`_can_stop_shared_proxysql()` が `False` を返すこと。
  - `IS_CLOUD` があり、`has_active_other_cloud_run_executions` が `True` の場合、`False` を返すこと。
  - `IS_CLOUD` があり、`has_active_other_cloud_run_executions` が `False` の場合、`True` を返すこと。
  - `main()` 実行時に条件を満たさない場合は `scale_proxysql_mig` が呼ばれないこと。
- `src/crawler/tests/unit/test_workflows_orchestration_568.py`:
  - ワークフロー定義のテストを最新の仕様（Workflows 側で無条件停止を行わないこと、ML パイプライン実行やエラーハンドリングが適切であること）に更新。
