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

### 1.4 スキップ物件・パーサー不備物件の抽出除外実装 (`_fetch_target_snapshots_once` / `_extract_expired_from_evaluations`)
1. **スキャン段階での除外**:
   - `PropertyEvaluation.objects.filter(is_published=True).exclude(needs_parser_fix=True).exclude(needs_recrawl=True)` により、パーサー不備フラグや再クロールフラグが立っているレコードをクエリ時点で除外する。
2. **評価レコード抽出時 (`_extract_expired_from_evaluations`)**:
   - `ev.get("needs_parser_fix")` または `ev.get("needs_recrawl")` が True の場合はキューイングせずスキップする。
3. **東急リバブル等の成約・掲載終了物件判定 (`tokyuParser.py` / `baseParser.py`)**:
   - `check_tokyu_listing_ended` で Next.js の `__NEXT_DATA__` 内の `isExpired=True` や検索結果テンプレート（`/templates/bui-*`）へのフォールバック（`summary` 欠損）を検知し、`ListingEndedException` を送出する。
   - `baseParser.py` の `LISTING_ENDED_BODY_KEYWORDS` にミサワホーム等の文言（「現在、こちらの物件は掲載を停止しております」等）を追加。
