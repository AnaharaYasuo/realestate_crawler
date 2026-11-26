# クローラー終了時刻（カットオフ）指定仕様 (SSOT)

- **関連 Issue**: #1845
- **対象モジュール**:
  - `src/crawler/package/utils/stop_time.py`
  - `src/crawler/main.py`
  - `src/crawler/scripts/ops/run_all_crawlers.py`

## 1. 目的

日次クローリング実行および単独クローラー CLI 実行において、指定した終了時刻（例: 昼前の `11:30` JST）に到達した時点で安全にクロールを打ち切って終了できるようにする。
これにより、日次バッチが日中帯まで無制限に走り続けることを防ぐ。

## 2. 設定インターフェース

| 手段 | キー / 引数 | 形式 | デフォルト |
|---|---|---|---|
| CLI 引数 (`main.py`) | `--stop-time=HH:MM` または `STOP_TIME=HH:MM` | 24時間表記 `HH:MM`（`00:00`〜`23:59`）、無効化は `none` / `off` / `disabled` / 空文字 | 環境変数 `CRAWLER_STOP_TIME` にフォールバック（未設定時は無効） |
| CLI 引数 (`run_all_crawlers.py`) | `--stop-time HH:MM` | 同上 | 環境変数 `CRAWLER_STOP_TIME`、未設定時は **`11:30`**（日次実行標準） |
| 環境変数（共通） | `CRAWLER_STOP_TIME` | 同上 | `main.py`: なし（無効）、`run_all_crawlers.py`: `11:30` |
| タイムゾーン環境変数 | `CRAWLER_STOP_TIME_TZ` | IANA タイムゾーン名 | `Asia/Tokyo`（JST / UTC+9） |

## 3. デッドライン計算ルール (`compute_stop_deadline`)

基準時刻 `now`（`CRAWLER_STOP_TIME_TZ` タイムゾーン）と指定時刻 `stop_time`（`datetime.time`）から、次の到達時刻 `deadline` を一意に決定する。

1. `now.time() < stop_time` の場合: **当日** の `stop_time` を `deadline` とする。
   - 例: 00:13 JST 開始、指定 `11:30` → 当日 11:30 JST
2. `now.time() >= stop_time` の場合: **翌日** の `stop_time` を `deadline` とする。
   - 例: 23:00 JST 開始、指定 `11:30` → 翌日 11:30 JST

## 4. 終了時刻到達時の挙動

### 4.1 単独 CLI 実行 (`src/crawler/main.py`)
- `start_stop_time_watchdog(deadline, on_stop)` をデーモンスレッドで起動する。
- デッドライン到達時:
  1. `[StopTimeCutoff]` ログを出力する。
  2. `stop.flag` を書き出す。
  3. `_shutdown_local_worker_executor_nonblocking()`、メトリクス保存（`export_job_metrics`）、進捗ファイル削除（`cleanup_crawler_progress`）を試行する。
  4. `os._exit(0)` で正常終了する。

### 4.2 日次バッチ実行 (`src/crawler/scripts/ops/run_all_crawlers.py`)
- デフォルトで `11:30` JST をカットオフ時刻として設定する（`--stop-time none` または `CRAWLER_STOP_TIME=none` で無効化可能）。
- メインループの各反復で `is_stop_time_reached(stop_deadline)` を評価する。
- デッドライン到達時:
  1. `[StopTimeCutoff]` ログを出力する。
  2. 実行中の全子プロセス（`active_processes`）へ停止シグナル（`terminate()` → 猶予後 `kill()`）を送信し回収する。
  3. 未着手の `pending_jobs` を空にして新規ジョブ投入を打ち切り、メインループを抜けて通常のサマリーレポート出力・後処理へ進む。
  4. カットオフ停止されたジョブは `status="stopped_by_cutoff"`（失敗カウント対象外）として記録する。
