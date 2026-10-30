# 内部設計書: 全体パイプライン（CRAWL_JOBS / ML）へのリガイド（RE-Guide）組み込み (Issue #953)

## 1. 修正対象モジュールと詳細

### 1.1 `src/crawler/package/utils/crawl_jobs.py`
- `CRAWL_JOBS` リストの投資用セクションまたは末尾に `("reguide", "investment")` を追加。
- 参照関係:
  - `run_all_crawlers.py`: `CRAWL_JOBS` をもとに実行タスクを展開。
  - `crawl_job_catalog.py`: `_match_start_class("reguide", "investment")` が `package/api/reguide.py` の `ParseReguideInvestmentStartAsync` を解決し、`routes/reguide_routes.py` の `REGUIDE_INVESTMENT_ROOT_URL` からシードURLを取得。

### 1.2 `src/crawler/package/ml/constants.py`
- `COMPANIES` タプル/リストに `"reguide"` を追加。
  ```python
  COMPANIES = [
      ...,
      "heim", "sumirin", "keio", "kenbiya", "ietan", "haseko", "adcast", "toho", "reguide",
  ]
  ```
- 影響範囲:
  - `src/crawler/package/ml/training/data_loader.py`:
    `collect_model_classes_by_type()` が `model.__name__.lower().startswith("reguide")` を検出し、`ReguideInvestment`（`apartment` 種別フォールバック）を学習データとして収集。
  - `src/crawler/package/ml/evaluation/targets.py`:
    `get_all_property_models()` が `reguide` で始まるモデルクラス `ReguideInvestment` を評価対象として収集。
  - `src/crawler/package/ml/evaluation/record_builder.py`:
    `resolve_company_and_type()` が `company="reguide"`, `property_type="investment"` を返却。
    `"investment" in property_type` が成立するため、`evaluate_investment_property()` が呼び出され収益性指標が計算される。

## 2. テスト設計
- `src/crawler/tests/unit/test_crawl_jobs_integration_reguide_953.py` を新規作成:
  - `("reguide", "investment") in CRAWL_JOBS` を検証。
  - `"reguide" in COMPANIES` を検証。
  - `build_catalog()[("reguide", "investment")]` が正しく解決されることを検証。
  - `main.get_dispatch_map()[("reguide", "investment")]` が存在することを検証。
- 既存テスト `test_crawl_job_catalog_sync.py` の実行による全件通過確認。
