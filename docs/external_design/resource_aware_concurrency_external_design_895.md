# 外部設計書: マシン余剰リソースに応じた動的並列度調整 (Issue #895)

## 1. システム構成とインターフェース
`package.utils.resource_limiter` または `package.api.adaptive_concurrency` にリソース検知・並列度決定モジュールを配置し、`run_all_crawlers.py` の `parse_args()` およびジョブ制御がこれを参照する。

### 1.1 関数仕様: `get_resource_aware_concurrency()`
```python
def get_resource_aware_concurrency(
    default_parallel: int = 9,
    default_playwright_parallel: int = 3,
) -> tuple[int, int, str]:
    """
    実行環境のメモリ制限・空きリソースを判定し、
    (safe_parallel, safe_playwright_parallel, reason_str) を返す。
    """
```

### 1.2 ログ・CLI インターフェース
- 起動時ログ出力例:
  ```text
  [INFO] 🧠 [Resource Awareness] Detected available memory: 3950MB (cgroup limit). Safe concurrency applied: parallel=3, playwright_parallel=1
  ```
- 環境変数指定時のログ出力例:
  ```text
  [INFO] 🧠 [Resource Awareness] Detected available memory: 3950MB, but overridden by environment variables: parallel=4, playwright_parallel=1
  ```

## 2. 外部影響と互換性
- **既存のテストコード**:
  - `test_adaptive_concurrency_795.py` や `test_local_docker_crawler_config.py` では、環境変数が未設定かつメモリ検知がモックまたは既定（8GB超）の場合は従来の 9 / 3 を返すため後方互換性を保持する。
  - テスト環境でメモリ制限がない場合は 9 / 3 となり、契約テストを破壊しない。
