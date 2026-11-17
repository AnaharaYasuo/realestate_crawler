# 外部設計書: Issue #1474 TTL再クロールの日次クォータ平滑化および社別均等配分

## 1. CLI インターフェース設計 (`run_ttl_expired_recrawl.py`)

### 1.1 新規追加・拡張引数
| 引数 | 型 | デフォルト値 | 説明 |
| :--- | :--- | :--- | :--- |
| `--daily-quota` | `int` | `None` | 1回の実行でクロールする全体上限件数。`--limit` と同義として扱うか、併用時は小さい方を優先。 |
| `--company-ratio-quota` | `int` | `None` | 各社ごとのTTL経過件数をこの分割数（例: 14日分割なら `14`）で割った件数（`ceil(count / ratio)`、最低1件）を社別上限とする。 |
| `--company-quota` | `int` | `None` | 各社ごとの絶対上限件数（一律固定数でキャップする場合に使用）。 |

### 1.2 実行例
```bash
# 14日均等配分（社別 1/14 クォータ配分 ＋ 全体 8,500件上限）
python src/crawler/scripts/ops/run_ttl_expired_recrawl.py --ensure-local-prod-infra --company-ratio-quota 14 --daily-quota 8500

# ドライランで配分件数の確認
python src/crawler/scripts/ops/run_ttl_expired_recrawl.py --ensure-local-prod-infra --company-ratio-quota 14 --daily-quota 8500 --dry-run
```

## 2. ログおよびサマリー出力設計
```text
[TTLRecrawl] Applied quota smoothing: total_before=117344 -> total_after=8402 across 20 companies (company_ratio_quota=14, daily_quota=8500).
[TTLRecrawl] Quota breakdown: {'mitsui': 2313, 'tokyu': 1646, 'homes': 1643, 'athome': 835, ...}
```
サマリー JSON に `quota_config` および `by_company_quota` を含め、日次バッチ結果の可観測性を担保する。

## 3. スキップ物件・パーサー不備物件の抽出除外設計
- `PropertyEvaluation` テーブルから再取得候補をスキャンする際、以下のいずれかに該当するレコードは通常TTL再クロール対象から除外する：
  1. `needs_parser_fix = True` または `needs_recrawl = True`（Auto-Healおよびパーサー改修パイプラインの別枠で管理）
  2. `is_published = False`（成約・掲載終了確定済み）
- これにより、パーサー改修待ちやエラー物件がTTL再取得に混入して無限リトライされるのを防止する。
