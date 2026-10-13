# 内部設計書: マシン余剰リソースに応じた動的並列度調整 (Issue #895)

## 1. モジュール配置
- ファイル: `src/crawler/package/utils/resource_limiter.py`
  - メモリ検知ロジック:
    1. cgroup v2 (`/sys/fs/cgroup/memory.max`)
    2. cgroup v1 (`/sys/fs/cgroup/memory/memory.limit_in_bytes`)
    3. `/proc/meminfo` (`MemAvailable` / `MemTotal`)
    4. `os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')`
  - 並列度算出ルール:
    - `mem_mb <= 4096`: `parallel = 3`, `playwright_parallel = 1`
    - `mem_mb <= 8192`: `parallel = 5`, `playwright_parallel = 2`
    - それ以外 (大容量 or 判定不能): `parallel = 9`, `playwright_parallel = 3`
  - 環境変数の統合:
    - `CRAWLER_PARALLEL` が数値で指定されている場合は、その値を `parallel` に採用。
    - `CRAWLER_PLAYWRIGHT_PARALLEL` が数値で指定されている場合は、その値を `playwright_parallel` に採用。

## 2. 呼出箇所
- `src/crawler/scripts/ops/run_all_crawlers.py`:
  - `parse_args()` 内で `get_resource_aware_concurrency()` を呼び出し、デフォルト引数の初期値を設定。
  - ジョブ開始時に INFO ログでリソース判定結果を出力。

## 3. テスト計画
- ファイル: `src/crawler/tests/unit/test_resource_aware_concurrency_895.py`
  1. メモリ 2GB / 4GB のモック時に `parallel=3`, `playwright_parallel=1` となること。
  2. メモリ 6GB / 8GB のモック時に `parallel=5`, `playwright_parallel=2` となること。
  3. メモリ 16GB / 制限なし時に `parallel=9`, `playwright_parallel=3` となること。
  4. 環境変数指定時にリソース判定より環境変数が優先されること。
  5. CLI引数指定時に環境変数およびリソース判定よりCLI引数が優先されること。
