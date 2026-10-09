# コンテナ内並列度最適化・適応型詳細並列度およびDB過負荷制御 外部設計書 (Issue #795)

## 1. 外部インターフェース仕様

### 1.1 CLI 引数変更仕様 (`run_all_crawlers.py`)
```bash
python src/crawler/scripts/ops/run_all_crawlers.py [OPTIONS]
```
| 引数 | デフォルト値（変更前） | デフォルト値（変更後） | 説明 |
| :--- | :--- | :--- | :--- |
| `--parallel` / `--standard-parallel` | `6` | **`9`** | 通常（標準）クローラープロセスの同時並行数（1.5倍に引き上げ） |
| `--playwright-parallel` | `3` | `3` | Playwright を使用する高メモリクローラープロセスの同時並行数 |

### 1.2 環境変数仕様
| 環境変数名 | デフォルト値 | 役割 |
| :--- | :--- | :--- |
| `CLOUD_DETAIL_CONCURRENCY` | `None` (未設定時は自動) | 詳細ページ取得の固定並行度。設定された場合は最優先で固定値として機能。 |
| `ENABLE_ADAPTIVE_DETAIL_CONCURRENCY` | `true` | 動的詳細並列度制御の有効化フラグ。 |
| `MAX_TOTAL_DETAIL_CONCURRENCY` | `36` | コンテナ全体で許容される詳細リクエストの総上限目安。 |
| `DB_OVERLOAD_THROTTLE_CONCURRENCY` | `2` | DB過負荷エラー検知時の緊急縮小詳細並列度。 |
| `SITE_CONCURRENCY_CAPS` | `nomura: 2, mitsui: 2, smtrc: 2` | WAF防護対象サイト向け詳細並行度強制制限キャップ。 |

### 1.3 IAM 構成 (Terraform)
- `crawler-runner` サービスアカウントに `roles/run.developer` を付与し、Cloud Workflows から `runWithOverrides`（引数・タスク数指定）による Cloud Run Job 起動を許可。

### 1.4 ログ・メトリクス出力
- **並列度決定ログ**:
  ```text
  [Concurrency] Active jobs in container: 1 -> Allocating detail concurrency: 15 (Max allowed)
  [Concurrency] Active jobs in container: 8 -> Allocating detail concurrency: 4
  ```
- **DB過負荷スロットリング発動ログ**:
  ```text
  [DB Throttling] Database overload detected (1040: Too many connections). Throttling detail concurrency to 2 and backing off for 3s...
  ```
