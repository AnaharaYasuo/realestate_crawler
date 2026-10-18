# Cloud定期実行ポータル除外および件数順優先処理 内部設計書 (Issue #985)

## 1. モジュール変更一覧

| ファイルパス | 変更種別 | 責務・変更内容 |
|---|---|---|
| `src/crawler/package/utils/crawl_jobs.py` | 変更 | `is_cloud_environment()` 判定ヘルパー追加。`filter_crawl_jobs()` において `skip_portals=None` 時に環境変数（`IS_CLOUD=true` または `CRAWL_SKIP_PORTALS=true`）に基づくデフォルト解決を実装。また `get_job_priority_score()` を提供。 |
| `src/crawler/package/utils/crawler_scheduler.py` | 変更 | 会社・物件種別の取扱件数に基づく優先度スコア計算関数 `calculate_job_priority(company, ptype)` を定義。各端末のジョブキューを優先度降順でソートする `sort_jobs_by_priority(jobs)` を実装。 |
| `src/crawler/scripts/ops/run_all_crawlers.py` | 変更 | `parse_args()` において、`skip_portals` のデフォルト値を `is_cloud_environment()` に基づいて決定。各端末で `target_jobs` を分割後、`job_queue = sort_jobs_by_priority(target_jobs)` として件数が多い順にキューを初期化。 |
| `src/crawler/scripts/ops/run_pipeline.py` | 変更 | `parse_args()` において `skip_portals` のデフォルト値を `is_cloud_environment()` に基づいて決定。 |
| `src/crawler/scripts/ops/run_ml_pipeline.py` | 変更 | `parse_args()` において `skip_portals` のデフォルト値を `is_cloud_environment()` に基づいて決定。集約レポート送信時の `total_jobs` 算出に反映。 |
| `src/crawler/scripts/ops/run_bulk_ml_evaluation.py` | 変更 | `parse_args()` において `skip_portals` のデフォルト値を `is_cloud_environment()` に基づいて決定。 |
| `src/crawler/tests/unit/test_cloud_skip_portals_and_prioritized_crawl_985.py` | 新規 | Issue #985 の全受入基準を検証する網羅的ユニットテスト。 |

---

## 2. 詳細設計

### 2.1 Cloud環境判定およびポータルスキップ解決ロジック (`crawl_jobs.py`)

```python
def is_cloud_environment() -> bool:
    """Cloud Run / Cloud Workflows 等のクラウド実行環境であるかを判定"""
    return os.getenv("IS_CLOUD", "").lower() in ("true", "1") or os.getenv("CRAWL_SKIP_PORTALS", "").lower() in ("true", "1")
```

各 CLI 引数パーサー（`run_pipeline.py`, `run_all_crawlers.py`, `run_ml_pipeline.py`, `run_bulk_ml_evaluation.py`）:
```python
# 既存の store_true 形式を維持しつつ、環境変数による既定値をサポート
is_cloud = is_cloud_environment()
parser.add_argument(
    "--skip-portals",
    dest="skip_portals",
    action="store_true",
    default=is_cloud,
    help="Skip large portal sites (athome, homes)",
)
parser.add_argument(
    "--no-skip-portals",
    dest="skip_portals",
    action="store_false",
    help="Do not skip portal sites even on Cloud environment",
)
```

### 2.2 「大手仲介優先 ➔ マンション優先」の2軸優先ソートロジック (`crawler_scheduler.py`)

ユーザー指示に基づくシンプルな2軸優先順位タプル `(is_major_broker, is_mansion)` を算出し、降順ソート：

1. **軸1 (第1優先): 大手仲介グループ**:
   - `mitsui`, `sumifu`, `tokyu`, `nomura`, `misawa`（大手仲介5社）
   - `smtrc`, `sumai1`, `mizuho`（信託3社）
   - `daikyo`（大京穴吹不動産）
   - これらに合致する場合は `is_major_broker = 1`、その他は `0`

2. **軸2 (第2優先): マンション種別**:
   - `mansion` の場合は `is_mansion = 1`、その他（`kodate`, `tochi`, `invest_*` 等）は `0`

3. **優先順位マトリクス**:
   1. 大手仲介 × マンション `(1, 1)`（最優先）
   2. 大手仲介 × その他種別 `(1, 0)`
   3. その他仲介 × マンション `(0, 1)`
   4. その他仲介 × その他種別 `(0, 0)`

```python
def calculate_job_priority(company: str, property_type: str) -> tuple[int, int]:
    is_major_broker = 1 if company.lower() in MAJOR_BROKER_COMPANIES else 0
    is_mansion = 1 if property_type.lower() == "mansion" else 0
    return (is_major_broker, is_mansion)

def sort_jobs_by_priority(jobs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(jobs, key=lambda j: calculate_job_priority(j[0], j[1]), reverse=True)
```

各端末での起動時（`run_all_crawlers.py`）：
```python
job_queue = sort_jobs_by_priority(list(target_jobs))
```
これにより、割り当てられたジョブの中で最も重いジョブが先頭に並び、`select_next_job` が可能な並行度スロットの許す限り最大件数のサイトから優先して起動する。

---

## 3. テスト計画 (TDD)
- `test_is_cloud_environment`: `IS_CLOUD=true`, `CRAWL_SKIP_PORTALS=true`, 未設定時の判定確認。
- `test_cli_default_skip_portals`:
  - `IS_CLOUD=true` のとき、`run_all_crawlers.py`, `run_pipeline.py`, `run_ml_pipeline.py`, `run_bulk_ml_evaluation.py` の引数未指定時の `skip_portals` が `True` になること。
  - `--no-skip-portals` を渡したとき `False` に上書きできること。
  - ローカル（`IS_CLOUD` なし）のとき、デフォルトが `False` であること。
- `test_sort_jobs_by_priority`:
  - ポータル ➔ 大手5社 ➔ 投資用/信託 ➔ 電鉄・ハウスメーカー ➔ 中小の順序でソートされること。
  - 同一会社内では `mansion` ➔ `kodate` ➔ `tochi` の順序で並ぶこと。
- `test_cloud_aggregation_without_portals`:
  - `IS_CLOUD=true` 時に集約レポートの母数が 82 件（または 96 件）となり、未実行誤警報が出ないこと。
