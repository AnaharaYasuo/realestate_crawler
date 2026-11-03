# 仕様書: ローカル本番実行とクラウド本番実行における負荷・並列度設定の環境別完全分離 (Issue #1211)

## 1. 概要
ローカル本番実行（ホストPCのCPU・メモリリソースを用いてCloud SQL/GCSへ保存・実行する運用形態）において、マシンスペックに応じた負荷制御（プロセス並列数、スレッドプール上限、詳細取得並行度）を安全に行えるようにするとともに、Cloud Run等のクラウド実行環境（`IS_CLOUD=true`）向けの大規模並列設定と設定値を完全に分離・独立して制御可能にする。

---

## 2. 環境変数体系と解決優先順位 (Resolution Hierarchy)

クローラーパイプラインが実行環境（クラウドかローカルか）を自動判別し、以下の優先順位で環境変数を解決する。
実行環境判定は `is_cloud_environment()`（`IS_CLOUD=true` または `CRAWL_SKIP_PORTALS=true`）に準拠する。

### 2.1. プロセス並列数 (`CRAWLER_PARALLEL`)
1. クラウド環境時:
   `CLOUD_CRAWLER_PARALLEL` ➔ `CRAWLER_PARALLEL` ➔ メモリ自動判定値（HighMemory: デフォルト 7）
2. ローカル環境時:
   `LOCAL_CRAWLER_PARALLEL` ➔ `CRAWLER_PARALLEL` ➔ メモリ自動判定値（HighMemory: デフォルト 7）

### 2.2. Playwright ブラウザ並列数 (`CRAWLER_PLAYWRIGHT_PARALLEL`)
1. クラウド環境時:
   `CLOUD_CRAWLER_PLAYWRIGHT_PARALLEL` ➔ `CRAWLER_PLAYWRIGHT_PARALLEL` ➔ メモリ自動判定値（HighMemory: デフォルト 3）
2. ローカル環境時:
   `LOCAL_CRAWLER_PLAYWRIGHT_PARALLEL` ➔ `CRAWLER_PLAYWRIGHT_PARALLEL` ➔ メモリ自動判定値（HighMemory: デフォルト 3）

### 2.3. プロセス内ローカルワーカースレッドプール上限 (`CRAWLER_LOCAL_WORKER_CONCURRENCY`)
各プロセスが詳細ページ処理（パース、DB保存）を並行実行する `ThreadPoolExecutor` のスレッド数上限。
1. クラウド環境時:
   `CLOUD_CRAWLER_LOCAL_WORKER_CONCURRENCY` ➔ `CRAWLER_LOCAL_WORKER_CONCURRENCY` ➔ デフォルト `3`
2. ローカル環境時:
   `LOCAL_CRAWLER_LOCAL_WORKER_CONCURRENCY` ➔ `CRAWLER_LOCAL_WORKER_CONCURRENCY` ➔ デフォルト `3`

### 2.4. 詳細ページ取得並行度 (`DETAIL_CONCURRENCY`)
1. クラウド環境時:
   `CLOUD_DETAIL_CONCURRENCY` ➔ `DETAIL_CONCURRENCY` ➔ `AdaptiveConcurrencyController` 自動算出
2. ローカル環境時:
   `LOCAL_DETAIL_CONCURRENCY` ➔ `DETAIL_CONCURRENCY` ➔ `AdaptiveConcurrencyController` 自動算出

---

## 3. 実装方針
- `src/crawler/package/utils/resource_limiter.py`:
  - `is_cloud_environment()` を導入し、`get_resource_aware_concurrency()` 内で `CLOUD_*` / `LOCAL_*` プレフィックス付き変数を優先解決。
- `src/crawler/package/api/api.py`:
  - `_get_local_worker_concurrency()` において `CLOUD_CRAWLER_LOCAL_WORKER_CONCURRENCY` / `LOCAL_CRAWLER_LOCAL_WORKER_CONCURRENCY` を優先解決。
- `src/crawler/package/api/adaptive_concurrency.py`:
  - `calculate_detail_concurrency()` において `CLOUD_DETAIL_CONCURRENCY` / `LOCAL_DETAIL_CONCURRENCY` を環境に応じて優先解決。
