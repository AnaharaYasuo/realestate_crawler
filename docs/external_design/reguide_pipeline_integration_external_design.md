# 外部設計書: 全体パイプライン（CRAWL_JOBS / ML）へのリガイド（RE-Guide）組み込み (Issue #953)

## 1. システム構成・連携フロー
RE-Guide（リガイド）のクローリングおよびML評価は、既存のパイプラインアーキテクチャに完全に統合される。

```
[run_pipeline.py / run_all_crawlers.py]
   │
   ├─ Step 1: Parallel Crawling
   │    └─ CRAWL_JOBS より ("reguide", "investment") を読み出し、
   │       main.py:reguideInvestmentStart -> ParseReguideInvestmentStartAsync を実行
   │       -> DB (reguide_investment テーブル) に物件保存
   │
   ├─ Step 2: ML Model Training (run_ml_pipeline.py)
   │    └─ COMPANIES の "reguide" により data_loader.py が
   │       ReguideInvestment (apartment種別マッピング) を学習データとして抽出
   │
   └─ Step 3: Bulk ML Evaluation (run_bulk_ml_evaluation.py)
        └─ targets.py が ReguideInvestment を取得
        └─ record_builder.py / investment_evaluator.py が利回り・NOI・DSCR等を算出して
           PropertyEvaluation テーブルへ永続化
```

## 2. インターフェース仕様変更

### 2.1 CRAWL_JOBS 定義
- `src/crawler/package/utils/crawl_jobs.py` の `CRAWL_JOBS` 末尾に以下を追加:
  ```python
  ("reguide", "investment"),
  ```

### 2.2 COMPANIES 定義
- `src/crawler/package/ml/constants.py` の `COMPANIES` 末尾に以下を追加:
  ```python
  "reguide",
  ```

## 3. 運用・実行影響
- CLI コマンド例:
  - 単体実行: `python main.py --company=reguide --type=investment`
  - サイト指定実行: `python src/crawler/scripts/ops/run_all_crawlers.py --sites=reguide:investment`
  - 全体パイプライン実行: `python src/crawler/scripts/ops/run_pipeline.py`（自動的に巡回対象に含まれる）
