# 内部設計書: ワーカー並行度 10 抑制およびプロセス並列数 7 拡張 (Issue #1037)

## 1. 変更詳細

### 1.1 `src/crawler/package/api/api.py`
```python
def _get_local_worker_concurrency() -> int:
    try:
        val = int(os.getenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "10"))
        return val if val > 0 else 10
    except (ValueError, TypeError):
        return 10
```

### 1.2 `src/crawler/package/utils/resource_limiter.py`
- MediumMemory（4GB超〜8GB以下）枠の並列数を `5` ➔ `7` に引き上げ。
- デフォルト引数 `default_parallel` を `7` に更新。

### 1.3 `src/crawler/scripts/ops/run_all_crawlers.py`
- `parse_args()` における `default_parallel = 7` に更新。
