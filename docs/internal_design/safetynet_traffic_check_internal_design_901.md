# 内部設計書: ProxySQL中断判定におけるトラフィック閾値チェック機能 (#901)

## 1. モジュール修正仕様
### `src/crawler/scripts/ensure_resources_stopped.py`
- 定数追加:
  - `DEFAULT_TRAFFIC_WINDOW_SEC: float = 600.0` (10分)
  - `DEFAULT_TRAFFIC_THRESHOLD_BYTES: int = 1_048_576` (1 MB)
  - `DEFAULT_MAX_UPTIME_SEC: float = 28_800.0` (8時間)
- 関数新設:
  - `_get_instance_network_received_bytes(project_id: str, zone: str, instance_name: str, window_sec: float = DEFAULT_TRAFFIC_WINDOW_SEC) -> tuple[int | None, str]`
    - `monitoring_v3` または REST API (`https://monitoring.googleapis.com/v3/projects/{project}/timeSeries`) を使用。
    - 取得不可やエラー時は `(None, error_message)` を返却し安全にフォールバック。
- `check_and_stop_proxysql_instance` 関数の拡張:
  1. `uptime > max_uptime_sec` の場合:
     - `warning_msg` 送信後、直ちに `_stop_instance` を呼び出して `forced_stop=True`, `skipped_reason="max_uptime_exceeded"` を返却。
  2. `active_jobs` が 0 件の場合:
     - `_get_instance_network_received_bytes` を呼び出し。
     - 受信バイト数が `DEFAULT_TRAFFIC_THRESHOLD_BYTES` 以上の場合:
       - `skipped_reason="active_traffic"` で停止をスキップし、Slack に継続通知を送信。
     - 受信バイト数が閾値未満または None の場合:
       - 従来通り `_stop_instance` を実行。

## 2. 単体テスト仕様
### `src/crawler/tests/unit/test_safetynet_traffic_check_901.py`
- `test_active_traffic_skips_stop`:
  - Cloud Run Job 0件、受信トラフィック 2 MB ➔ `was_leaked=False`, `skipped_reason="active_traffic"`, 停止なし。
- `test_low_traffic_triggers_stop`:
  - Cloud Run Job 0件、受信トラフィック 50 KB ➔ `was_leaked=True`, `forced_stop=True`, `_stop_instance` 実行。
- `test_max_uptime_exceeded_forces_stop`:
  - 稼働時間 9時間（32400s）、トラフィック 5 MB ➔ 上限超過により `forced_stop=True`, `_stop_instance` 実行。
- `test_monitoring_error_falls_back_to_stop`:
  - モニタリングAPIエラー時 ➔ 停止処理へ安全にフォールバック。
