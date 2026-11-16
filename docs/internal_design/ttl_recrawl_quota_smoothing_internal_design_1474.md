# 内部設計書: Issue #1474 TTL再クロールの日次クォータ平滑化および社別均等配分

## 1. モジュールおよび関数設計 (`src/crawler/scripts/ops/run_ttl_expired_recrawl.py`)

### 1.1 クォータ平滑化関数 `apply_quota_smoothing`
```python
def apply_quota_smoothing(
    targets: list[TtlTarget],
    daily_quota: int | None = None,
    company_quota: int | None = None,
    company_ratio_quota: int | None = None,
) -> list[TtlTarget]:
    """Apply daily overall quota and per-company quota smoothing while preserving company interleaving."""
```

#### ロジック詳細:
1. `targets` を `target.company.lower()` ごとにグルーピング（`buckets: dict[str, list[TtlTarget]]`）。
2. 各会社について、許容される最大件数 `allowed_count` を決定：
   - `company_quota` が指定されている場合: `min(len(targets), company_quota)`
   - `company_ratio_quota` が指定されている場合（例: 14）: `min(len(targets), max(1, math.ceil(len(targets) / company_ratio_quota)))`
   - 両方指定されている場合は小さい方、未指定の場合は会社ごとの上限なし。
3. 各社のリストを `allowed_count` 件でスライス。
4. 各社のスライス済みリストを `interleave_targets_by_company` に渡してラウンドロビンでインターリーブ。
5. 全体上限 `effective_limit`（`daily_quota` または `--limit`）が指定されている場合、インターリーブ後のリストを `[:effective_limit]` でスライス。
6. 平滑化後の対象リストを返却。

### 1.2 `collect_ttl_expired_targets` への統合
- 引数に `daily_quota`, `company_quota`, `company_ratio_quota` を追加。
- 抽出完了後、クォータ平滑化関数を呼び出して返却。

### 1.3 `build_arg_parser` への追加
- `--daily-quota` (type=int, default=None)
- `--company-quota` (type=int, default=None)
- `--company-ratio-quota` (type=int, default=None)
