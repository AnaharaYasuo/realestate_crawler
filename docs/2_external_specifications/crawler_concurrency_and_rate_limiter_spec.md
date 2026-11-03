# Specification: Crawler Concurrency & Rate Limiter Fix

## 1. 概要 (Overview)
クローラー実行時、一覧ページから詳細ページへのローカルディスパッチ処理において以下の2つの問題が発生し、300秒無進捗ハング (`HangSilentFailure`) や 2時間待機タイムアウト (`TimeoutError`) を引き起こしていた。
1. **ワーカープール並行度とパーサー規定値の不整合**:
   各パーサーで `DETAIL_PARARELL_LIMIT = 3` と定めているにもかかわらず、`api.py` のローカルワーカープールがデフォルト 10 スレッド（`CRAWLER_LOCAL_WORKER_CONCURRENCY = 10`）で動作し、各スレッドが個別イベントループとHTTPセッション・コネクタを立ち上げるため過負荷・通信詰まり・WAF遮断を誘発していた。
2. **レートリミット（`SITE_DOWNLOAD_DELAYS`）の未来時刻累積バグ**:
   `scheduled_time = max(now, next_allowed)` および `self._SITE_NEXT_ALLOWED[company] = scheduled_time + effective_delay` の計算により、大量のタスクが並ぶと `scheduled_time` が未来時刻に向かって線形に積み上がり、後続タスクの待機時間（`scheduled_time - now`）が数百〜数千秒に達してプロセスを停止させていた。

本改修では、これらを是正して安全かつ安定したクローリングを保証する。

---

## 2. 変更仕様 (Specifications)

### 2.1 デフォルト並行度の是正 (`CRAWLER_LOCAL_WORKER_CONCURRENCY`)
- `_get_local_worker_concurrency()` のデフォルト値を `10` から `3` に変更する。
- 環境変数 `CRAWLER_LOCAL_WORKER_CONCURRENCY` が設定されている場合はその値を尊重する（正の整数）。

### 2.2 レートリミット計算のバグ是正 (`_apply_download_delay_if_needed`)
- `_SITE_NEXT_ALLOWED[company]` の未来時刻加算において、最大待機時間を `effective_delay`（または安全な上限閾値）に制限する。
- 過去や未来に過剰に乖離したスケジュール時刻をリセットし、現在時刻 `now` を基準としたスライディングウィンドウ方式にする。
- 具体的には：
  ```python
  with self._SITE_RATE_LOCK:
      now = time.monotonic()
      next_allowed = self._SITE_NEXT_ALLOWED.get(company, now)
      effective_delay = delay / max(1, self._getPararellLimit())
      # next_allowed が現在時刻より古すぎる場合は now にリセット
      # next_allowed が現在時刻より遠すぎる未来（effective_delay * 並行度以上）にある場合はキャップする
      base_time = max(now, next_allowed)
      max_future = now + effective_delay * max(1, self._getPararellLimit())
      scheduled_time = min(base_time, max_future)
      self._SITE_NEXT_ALLOWED[company] = scheduled_time + effective_delay
      wait_sec = scheduled_time - now
  ```
- これにより、待機時間 `wait_sec` は最大でも `effective_delay * 並行度`（通常 0.5〜1.5秒程度）以内に収まり、数百秒・数時間スリープするバグを完全に排除する。

---

## 3. テスト計画 (Test Plan)
- `tests/unit/test_bounded_local_worker_1046.py`: デフォルト並行度が 3 であること、および環境変数による上書きが動作することを確認。
- `tests/unit/test_rate_limiter_fix.py`: 1,000 件連続で `_apply_download_delay_if_needed` が呼ばれても、個々の待機時間が安全閾値（数秒以内）に収まり、数千秒に累積しないことを検証。
