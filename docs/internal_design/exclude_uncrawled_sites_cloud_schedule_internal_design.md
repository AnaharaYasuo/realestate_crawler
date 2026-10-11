# クラウド定期実行（スケジュール）における未巡回サイト除外内部設計書 (Issue #880)

## 1. 変更モジュール詳細

### 1.1 `src/crawler/package/utils/crawl_jobs.py`
- `UNCRAWLED_COMPANIES = {"kenbiya", "ietan", "haseko", "adcast", "toho"}` を定義。
- `PORTAL_COMPANIES = {"athome", "homes"}` をエクスポート（単一の正）。
- `filter_crawl_jobs()` に `skip_portals: bool = False`, `skip_uncrawled: bool = False` の両対応を追加、あるいは呼び出し側でフィルタリング。

### 1.2 `src/crawler/scripts/ops/run_all_crawlers.py`
- 引数に `--skip-uncrawled` を追加。
- `target_jobs` 抽出時に `args.skip_uncrawled` が真の場合、`UNCRAWLED_COMPANIES` を除外。

### 1.3 `src/crawler/scripts/ops/run_pipeline.py`
- 引数に `--skip-uncrawled` を追加。
- `target_jobs` 抽出および `_run_crawler_step` の `crawl_cmd` に `--skip-uncrawled` を伝播。
- `_run_post_crawl_pipeline` / `run_ml_pipeline.py` への伝播。

### 1.4 `src/crawler/scripts/ops/run_ml_pipeline.py` & `run_bulk_ml_evaluation.py` & `targets.py`
- `targets.py`: `get_all_property_models(skip_portals: bool = False, skip_uncrawled: bool = False)` に対応し、評価バッチからも除外。

### 1.5 Terraform / Workflows
- `terraform/scheduler.tf`: `skipUncrawled = true` を追加。
- `terraform/workflows/daily_pipeline.yaml`:
  - `initVars`: `skipUncrawled: ${default(map.get(args, "skipUncrawled"), true)}`
  - `buildCrawlerArgs`: `checkSkipUncrawled` ステップで `--skip-uncrawled` を `crawlerArgs` および `mlArgs` に追加。
