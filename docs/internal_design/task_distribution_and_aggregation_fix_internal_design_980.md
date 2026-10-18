# クローラータスク分散最適化および集約レポート母数是正 内部設計書 (Issue #980)

## 1. 概要
本設計書は、Issue #980 に基づくタスク負荷平準化（8タスク分散の再設計）および集約レポートの母数動的化の実装仕様を定義する。

## 2. モジュール別変更仕様

### 2.1 `src/crawler/package/utils/task_distribution.py`
- `_assign_8_task_index(c_lower: str, p_lower: str) -> int`:
  - 以下のルール順序で判定する：
    1. `homes` ➔ `5` (homes全種別 4 jobs)
    2. `athome` ➔ `6` (`p_lower == "mansion"` の場合), それ以外 ➔ `7`
    3. `p_lower in ("invest_kodate", "invest_apartment", "invest_building", "investment")` ➔ `3` (投資用・事業用全般 18 jobs)
    4. 大手5社 (`MAJOR_5_COMPANIES`):
       - `"mansion"` ➔ `0`
       - `"kodate"` ➔ `1`
       - `"tochi"` ➔ `2`
    5. `daikyo`:
       - `"mansion"` ➔ `0`
       - それ以外 (`"kodate"`, `"tochi"`) ➔ `1`
    6. 信託3社 (`TRUST_3_COMPANIES = {"smtrc", "sumai1", "mizuho"}`):
       - 居住用 ➔ `2` (大手5社 tochi 5件 + 信託3社居住用 9件 = 14 jobs)
    7. 中堅仲介 (`UNCRAWLED_COMPANIES = {"kenbiya", "ietan", "haseko", "adcast", "toho"}`):
       - 居住用・土地 ➔ `6` (athome mansion 1件 + 中堅仲介12件 = 13 jobs)
    8. 電鉄・ハウスメーカー系居住用 (`sekisui`, `afr`, `daiwa`, `totate`, `odakyu`, `sumirin`, `heim`, `rearie`, `keio`, `seibu`, `keikyu`, `sotetsu`, `keisei`):
       - `"mansion"` ➔ `7` (athomeその他3件 + 電鉄/ハウスメーカーmansion 13件 = 16 jobs)
       - それ以外 (`"kodate"`, `"tochi"`) ➔ `4` (26 jobs)

### 2.2 `src/crawler/package/utils/pipeline_coordinator.py`
- `aggregate_task_array_reports(task_records: list, total_jobs: int | None = None) -> dict`:
  - `total_jobs` が `None` の場合、`package.utils.crawl_jobs.CRAWL_JOBS` の長さを既定値として使用する（フォールバックとして 104）。

### 2.3 `src/crawler/scripts/ops/run_ml_pipeline.py`
- `send_aggregated_crawl_report(execution_date: datetime.date | None = None, total_jobs: int | None = None) -> bool`:
  - `total_jobs` の指定がない場合、`filter_crawl_jobs(skip_portals=..., skip_uncrawled=...)` を用いて、当日の実行オプションに応じたジョブ総数を動的に算出し、`aggregate_task_array_reports` へ渡す。

### 2.4 テストケース同期
- `src/crawler/tests/unit/test_crawl_speed_and_cost_optimization_851.py`:
  - 大京の再配置テストを更新し、信託系・電鉄系・中堅系の新分散テストを追加。
- `src/crawler/tests/unit/test_crawler_ml_split_549.py`:
  - `total_jobs` のテストアサーションを同期。
