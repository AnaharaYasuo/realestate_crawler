# Specification: Issue #1484 - Bulk Eval Concurrency Memory Optimization & Kenbiya Static Asset Blocking

## 1. 背景と課題
1. **Cloud Run Job (2GiB RAM) でのバルク価格推定 OOM**:
   - `realestate-ml-pipeline-prod` において、`BULK_EVAL_CONCURRENCY` が `8` に設定されていたため、8スレッドが同時に機械学習モデル（LightGBM, XGBoost, CatBoost, RandomForest）および取引事例比較マスタを展開し、コンテナメモリ上限 2GiB を超過して Exit Code -9 (SIGKILL / OOM) で異常終了した。
   - `package/ml/evaluation/runner.py` 内の `DEFAULT_CONCURRENCY` は既に `2` であるが、`terraform/cloud_run_job.tf` の環境変数およびジョブ実行時に `BULK_EVAL_CONCURRENCY=8` が注入されていた。これを `2` に抑制し、`run_ml_pipeline.py` からも安全に `--concurrency 2`（または環境変数デフォルト尊重）を渡せるようにする。
2. **健美家 (Kenbiya) Playwright ステルス取得時の静的アセット遮断**:
   - 健美家は F5 BIG-IP WAF により HTTP 403 / 429 が発生しやすい。
   - Playwright によるフォールバック取得（`_fetch_with_playwright`）時に画像・CSS・フォント等の不要な静的アセットをダウンロードすると、通信負荷やWAF検知リスク、メモリ消費が増大する。
   - 物件詳細のHTML本体（スペック・価格・間取り・賃料利回り等）のみを取得し、静的アセットは `page.route` で即座に遮断（`route.abort()`）する。

---

## 2. 設計方針

### 2.1 BULK_EVAL_CONCURRENCY 抑制
- `terraform/cloud_run_job.tf`:
  - `crawler_job` (L69): `BULK_EVAL_CONCURRENCY = "2"`
  - `ml_pipeline_job` (L571): `BULK_EVAL_CONCURRENCY = "2"`
- `src/crawler/scripts/ops/run_ml_pipeline.py`:
  - `eval_cmd` 呼び出し時に `["--concurrency", "2"]` を明示的に付与（環境変数やフラグによらず 2GiB 環境で確実に2並列以下で稼働）。

### 2.2 健美家 Playwright 静的アセット遮断
- `src/crawler/package/parser/kenbiyaParser.py`:
  - `_fetch_with_playwright(self, url: str) -> bytes`:
    ```python
    # 静的アセット（画像、CSS、フォント、メディア等）の取得を遮断して高速化・WAF負荷軽減
    await page.route(
        re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|ico|css|woff2?|ttf|eot)(\?.*)?$", re.IGNORECASE),
        lambda route: route.abort(),
    )
    ```

---

## 3. テスト計画
- `tests/unit/test_bulk_eval_memory_1484.py`:
  - `run_ml_pipeline.py` が `run_bulk_ml_evaluation.py` に `--concurrency 2` を渡すことを検証。
  - `KenbiyaParserBase._fetch_with_playwright` において静的アセットが遮断されるルート設定が登録されることを検証。
- アーキテクチャテスト (`test_architecture_harness.py`) および関連テストの実行。
