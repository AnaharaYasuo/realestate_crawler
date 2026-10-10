# 内部設計書: ローカル Docker クローラー実行制御 (Issue #857)

## 1. 修正対象モジュール

### 1.1. Terraform ファイアウォール定義 (`terraform/network.tf`)
- `google_compute_firewall.allow_iap_to_proxysql` リソースを追加。
  - `network`: `google_compute_network.vpc_network.id`
  - `source_ranges`: `["35.235.240.0/20"]` (Google Cloud IAP の固定 IP アドレスブロック)
  - `target_tags`: `["proxysql"]`
  - `allow`: `protocol = "tcp"`, `ports = ["6033", "22"]`

### 1.2. クローラー並列数引数パース (`src/crawler/scripts/ops/run_all_crawlers.py`)
- `parse_args()` において、環境変数からデフォルト値を取得するように改修。
  ```python
  default_parallel = int(os.getenv("CRAWLER_PARALLEL", "9"))
  default_playwright_parallel = int(os.getenv("CRAWLER_PLAYWRIGHT_PARALLEL", "3"))
  ```
  CLI オプション `--parallel` / `--playwright-parallel` が明示された場合は CLI が最優先。

### 1.3. 詳細並行度制御 (`src/crawler/package/api/adaptive_concurrency.py`)
- `calculate_detail_concurrency()` において、`CLOUD_DETAIL_CONCURRENCY` だけでなく `DETAIL_CONCURRENCY` 環境変数を認識するように拡張（`os.getenv("DETAIL_CONCURRENCY") or os.getenv("CLOUD_DETAIL_CONCURRENCY")`）。

### 1.4. Docker Compose 定義 (`docker-compose.yml`)
- `app` および `scheduler` サービスの環境変数定義において、ローカル上書きが可能な形式に変更。
  - `DB_HOST`: `${DB_HOST:-db}` (IAP トンネル利用時はホスト側の `host.docker.internal` を指定可能)
  - `DB_PORT`: `${DB_PORT:-3306}` (ProxySQL 経由時は `6033` を指定可能)
  - `STORAGE_BACKEND`: `${STORAGE_BACKEND:-minio}` (GCS 直接アップロード時は `gcs` を指定可能)
  - `CRAWLER_PARALLEL`: `${CRAWLER_PARALLEL:-4}`
  - `CRAWLER_PLAYWRIGHT_PARALLEL`: `${CRAWLER_PLAYWRIGHT_PARALLEL:-1}`
- ホスト側の Google ADC 認証情報（`~/.config/gcloud`）をマウントするためのボリューム定義を追加（コメントアウトまたは環境変数連動）。

## 2. 安全性担保 (Safety-Net)
- `run_pipeline.py` ではすでに `if not os.environ.get("IS_CLOUD"): return` が入っており、ローカル実行時に ProxySQL の起動・停止 API が呼ばれないことが担保されている。
- `DbLivenessMonitor` は `resolve_db_endpoint()` から `host, port` を取得して TCP 疎通を確認するため、`host.docker.internal:6033` でも透過的に死活監視が動作する。
