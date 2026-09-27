# CI/CD パイプライン最適化内部設計書 (Issue #456)

## 1. ワークフロー変更一覧

### 1.1 `.github/workflows/test.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
    push:
      branches: [ main, master, production ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
    push:
      branches: [ production ]
  ```
  ※ `push: [main, master]` を削除。本番デプロイ時の検証用として `production` のみ維持。

### 1.2 `.github/workflows/security-scan.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
      branches:
        - master
        - main
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - main
  ```

### 1.3 `.github/workflows/codeql.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - main
    schedule:
      - cron: '0 18 * * 0'
  ```

### 1.4 `.github/workflows/sonar.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
      branches: [ main, master ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
  ```

### 1.5 `.github/workflows/snyk.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
  ```

### 1.6 `.github/workflows/swagger-generate.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches: [ master, main, production ]
    push:
      branches: [ master, main ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ master, main, production ]
  ```

### 1.7 `.github/workflows/review-gate.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - production
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
  ```

## 2. GitHub ブランチ保護ルールの更新設計
- **対象ブランチ**: `production`
- **Required Status Checks**:
  - `["Verify Source Branch is master"]` (`production-gate.yml`)
- **理由**: `production-gate.yml` は `master` からの PR かどうかのみを高速（数秒）で判定するため、Release PR のボトルネックを完全解消する。

## 3. Live Crawl Guarantee Tests 分割設計 (Issue #525)
- **背景**:
  - `Live Crawl Guarantee Tests` が単一ジョブで実行されており、最大750秒（12分半）の長大タイムアウト枠を占有していた。
  - Playwrightヘビー会社（athome, mizuho, sekisui）と静的HTMLパーサー会社群（mitsui, sumifu, tokyu, nomura, etc.）が混在し、1社でも一時的通信エラーが発生した際に全件リトライが必要となっていた（例: `sumai1_mansion` 1件の失敗で全 83 ジョブを再実行）。
- **分割構成**:
  - `test.yml` のマトリクスジョブとして以下のように分割並列実行:

    | マトリクス名 | `CRAWL_LIVE_BUCKETS` | `CRAWL_LIVE_STATIC_SHARD` |
    |---|---|---|
    | `Live Crawl Guarantee (Static 1/2)` | `static` | `1/2` |
    | `Live Crawl Guarantee (Static 2/2)` | `static` | `2/2` |
    | `Live Crawl Guarantee (Playwright mizuho+sekisui)` | `pw-mizuho,pw-sekisui` | - |
    | `Live Crawl Guarantee (Playwright athome)` | `pw-athome` | - |

  - ウォールクロック上限: 各ジョブ `CRAWL_LIVE_WALL_LIMIT_SEC=300`。
  - 障害影響の極小化: 各ジョブが独立して実行され、GitHub Actions 上で個別に再実行可能。
- **実装 (`package.utils.live_parallel`)**:
  - `build_live_parallel_plan()` はバケット構築後、`CRAWL_LIVE_STATIC_SHARD=k/n` があれば静的ジョブを `index % n == k - 1` で絞り込み（空なら静的バケットを生成しない）、`CRAWL_LIVE_BUCKETS` があればラベル一致のバケットのみ残す。
  - 不正値（未知ラベル、`k/n` 形式違反、`k` が範囲外）は `ValueError` を送出し、CI の設定ミスを即時 FAIL させる（無言で 0 件実行・成功にしない）。
  - 検証: `tests/unit/test_live_parallel.py` で、CI 4 分割の対象ジョブ和集合が `CRAWL_JOBS` 全件と重複なく一致することを検証する。
