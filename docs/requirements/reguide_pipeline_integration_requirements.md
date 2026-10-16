# 要件定義書: 全体パイプライン（CRAWL_JOBS / ML）へのリガイド（RE-Guide）組み込み (Issue #953)

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**: 不動産投資データ収集・分析システムの運用者および利用者
* **目的**: RE-Guide（リガイド収益物件）を日次・定期クローリングおよびML機械学習・バルク価格推定の全体パイプラインに正式に組み込み、自動巡回からモデル評価までを一気通貫で実行可能にする。
* **価値**: 手動・単体実行に依存せず、基幹パイプラインの標準ジョブとしてリガイド投資物件の収集と投資性評価（利回り、NOI、DSCR、お宝判定等）を継続蓄積・更新できる。

## 2. 機能要件 (FR)

### FR-953-001: CRAWL_JOBS へのリガイド組み込み
- `src/crawler/package/utils/crawl_jobs.py` の `CRAWL_JOBS` に `("reguide", "investment")` を追加する。
- `run_all_crawlers.py`, `run_pipeline.py`, `run_dispatcher.py` を含むすべてのパイプラインランナーからリガイド投資物件が巡回対象として自動認識されること。

### FR-953-002: ML パイプライン定数 COMPANIES への追加
- `src/crawler/package/ml/constants.py` の `COMPANIES` に `"reguide"` を追加する。
- これにより、`data_loader.py`（学習データ抽出）および `targets.py`（バルク推論対象抽出）において `ReguideInvestment` モデルが自動検知され、ML学習およびバルク価格推定・お宝物件評価の対象に含まれること。

### FR-953-003: カタログ・ディスパッチ・フィルタ同期の保証
- `package/utils/crawl_job_catalog.py` による Start API / シード URL 解決テスト（`test_crawl_job_catalog_sync.py`）が全件パスすること。
- `main.py` の `get_dispatch_map()` と 100% 整合すること。

## 3. 非機能要件 (NFR)
- **NFR-953-001 (後方互換性)**: 既存の他社クローラーおよび ML 処理ロジックに影響を与えないこと（Micro-Diff 実装）。
- **NFR-953-002 (テスト網羅性)**: ユニットテスト・統合テストにおいて CRAWL_JOBS および COMPANIES の整合性が客観的に検証されていること。
