# 外部設計書: ワーカー並行度 10 抑制およびプロセス並列数 7 拡張 (Issue #1037)

## 1. 外部インターフェース仕様
- **環境変数 `CRAWLER_LOCAL_WORKER_CONCURRENCY`**:
  - 未指定時のデフォルト値を `10` とする。正の整数が指定された場合はその値を尊重する。
- **環境変数 `CRAWLER_PARALLEL`**:
  - デフォルト計算（MediumMemory: <=8GB）時の安全プロセス並列数を `7` とする。
  - `--parallel` 引数指定または環境変数 `CRAWLER_PARALLEL` でオーバーライド可能。

## 2. 影響範囲
- `src/crawler/package/api/api.py`: `_get_local_worker_concurrency()`
- `src/crawler/package/utils/resource_limiter.py`: `get_resource_aware_concurrency()`
- `src/crawler/scripts/ops/run_all_crawlers.py`: デフォルト並列数の整合
- 既存のユニットテスト・統合テスト
