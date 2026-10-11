# 基本設計書: Task 0 ハング防止・Watchdog即時検知・3時間タイムアウト・HTTPタイムアウト厳格化 (Issue #861)

## 1. システム構成と変更概要
本改修では、クローラーパイプラインのハング発生要因を排除し、万一のハング発生時にも確実にプロセスグループを強制終了させ、全体のタイムアウト上限を3時間に抑え込む多層防御（Defense in Depth）を構築する。

```mermaid
flowchart TD
    subgraph CloudRunJob["Cloud Run Job (Task Array)"]
        subgraph MasterProc["親プロセス: run_all_crawlers.py (3h Timeout: 10800s)"]
            Watchdog["Watchdog (600s 沈黙監視・全ジョブ巡回)"]
        end
        subgraph WorkerSubProc["子プロセス: main.py"]
            LocalExec["_handle_local_execution (120s タイムアウト上限)"]
            RateLimit["RateLimiter (threading.Lock によるスレッドセーフ化)"]
            HttpReq["HTTP Request (aiohttp ClientTimeout: 15s)"]
        end
    end
    subgraph SafetyNet["Safety-Net: ensure_resources_stopped.py"]
        HungGuard["DEFAULT_HUNG_THRESHOLD_SEC = 11400s (3h + 10m)"]
    end

    Watchdog -- "600s沈黙検知" -->|SIGKILL| WorkerSubProc
    HungGuard -- "11400s超過検知" -->|Cancel & Stop| CloudRunJob
```

## 2. モジュール別設計
### 2.1 `src/crawler/package/api/api.py`
- `_SITE_RATE_LOCKS`: `dict[str, threading.Lock]` に変更。
  - レートリミット計算（`time.monotonic() - last_time < delay`）の区間を `with self._SITE_RATE_LOCKS[company]:` で保護。スレッド間でイベントループが異なっても `RuntimeError` やロックハングが発生しない。
  - スリープは `time.sleep(delay - elapsed)` または `await asyncio.sleep(delay - elapsed)` を適切に使い分ける。
- `_handle_local_execution`:
  - 累積経過時間 `elapsed` を測定。
  - 最大実行時間（デフォルト120秒）を超過した場合はループを抜け、エラーログを出力して `(detail_url, 504, "LocalTimeout")` を返却。
- `_getContent`:
  - `aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)` を明示的に指定。

### 2.2 `src/crawler/scripts/ops/run_all_crawlers.py`
- `HANG_THRESHOLD_SEC` による進捗監視:
  - ループ内の `break` を撤廃。15秒以上経過したジョブすべてに対して DB カウントを取得し `last_act` を更新。
  - `active_processes` 初期化時に `(proc, company, ptype, now_ts, start_dt, now_ts, 0, now_ts)` と 8要素タプルとして定義し、インデックス整合性を担保。
  - `timeout_sec` のデフォルト値を 32400 から 10800 (3時間) に短縮。

### 2.3 `terraform/` & Safety-Net & Workflows
- `terraform/variables.tf`: `crawler_timeout` のデフォルトを `"10800s"`、バリデーション上限も `10800` に設定。
- `src/crawler/scripts/ensure_resources_stopped.py`:
  - `DEFAULT_HUNG_THRESHOLD_SEC` を `11400.0` (10800.0 + 600.0) に変更。
- `src/crawler/scripts/ops/run_pipeline.py`:
  - `DEFAULT_TIMEOUT_SEC` を `10800.0` に変更。
- `terraform/workflows/daily_pipeline.yaml`:
  - `rawCrawlTimeoutSec` を `10800` に変更。
  - `maxPipelineDurationSec` を `18000` (5時間) に最適化。
- `terraform/workflows/recrawl_anomalies_pipeline.yaml`:
  - `rawTimeoutSec` を `10800`、`maxPipelineDurationSec` を `10800` に変更。
