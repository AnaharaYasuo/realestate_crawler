# マルチイベントループ下でのレートリミット例外解消およびウォッチドッグ監視公平化 内部設計書 (Issue #860)

## 1. クラス・コンポーネント設計

### 1.1 `ParseDetailPageAsyncBase._apply_download_delay_if_needed`
`src/crawler/package/api/api.py`

#### 変更前 (Issue #807)
```python
_SITE_RATE_LOCKS: ClassVar[dict[str, asyncio.Lock]] = {}
_SITE_LAST_START_TIMES: ClassVar[dict[str, float]] = {}

async def _apply_download_delay_if_needed(self):
    ...
    if company not in self._SITE_RATE_LOCKS:
        self._SITE_RATE_LOCKS[company] = asyncio.Lock()

    async with self._SITE_RATE_LOCKS[company]:  # ★異なるイベントループからアクセスされると RuntimeError
        ...
```

#### 変更後 (Issue #860: アトミック・タイムスロット予約方式)
```python
_SITE_RATE_LOCK = threading.Lock()
_SITE_NEXT_ALLOWED: ClassVar[dict[str, float]] = {}

async def _apply_download_delay_if_needed(self):
    company = self._resolve_target_company()
    if not company:
        return
    delay = self.SITE_DOWNLOAD_DELAYS.get(company, 0.0)
    if delay <= 0.0:
        return

    with self._SITE_RATE_LOCK:
        now = time.monotonic()
        target = max(now, self._SITE_NEXT_ALLOWED.get(company, 0.0))
        self._SITE_NEXT_ALLOWED[company] = target + delay
        wait_sec = target - now

    if wait_sec > 0:
        await asyncio.sleep(wait_sec)
```

- **スレッド・イベントループ安全性**:
  - `threading.Lock` はプロセス内全スレッドで有効。
  - 排他制御区間は辞書の参照と加算（ナノ秒〜マイクロ秒単位）のみで完了するため、スレッドの競合や待機は発生しない。
  - 待機自体はロック解放後に `await asyncio.sleep(wait_sec)` で各イベントループが独立して非同期実行するため、イベントループをブロックしない。

---

### 1.2 `run_all_crawlers.py` ウォッチドッグ進捗監視ループ

`src/crawler/scripts/ops/run_all_crawlers.py`

#### 変更前
```python
if HANG_THRESHOLD_SEC > 0:
    for idx in tuple(active_processes.keys()):
        ...
        if (now - last_check_t) >= 15.0:
            counts = get_count_for_job(company, ptype, start_dt)
            current_db_cnt = counts[2] if counts[0] is not None else None
            if current_db_cnt is not None:
                if current_db_cnt > prev_db_cnt:
                    last_act = now
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
            else:
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)
            break  # ★先頭ジョブしかチェックされず、後続ジョブが600s間放置される
```

#### 変更後
```python
if HANG_THRESHOLD_SEC > 0:
    for idx in tuple(active_processes.keys()):
        ...
        if (now - last_check_t) >= 15.0:
            counts = get_count_for_job(company, ptype, start_dt)
            current_db_cnt = counts[2] if counts[0] is not None else None
            if current_db_cnt is not None:
                if current_db_cnt > prev_db_cnt:
                    last_act = now
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
            else:
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)
            # break を除去し、同ループ内で 15秒インターバルを迎えた他ジョブも公平に更新
```

---

## 2. テスト設計 (TDD)
1. `test_api_rate_limiter_860.py`:
   - 異なる 3 つのイベントループ（`asyncio.new_event_loop()` を実行する別スレッド）から同時に `_apply_download_delay_if_needed()` を呼び出し、例外（`RuntimeError`）が発生しないこと、および実行間隔が適切に保たれることをアサート。
2. `test_crawler_watchdog_fairness_860.py`:
   - 複数ジョブが並行実行されている状況をシミュレートし、監視ループのイテレーションにおいて全アクティブジョブの `last_check_t` および `last_act` が適切に更新されることをアサート。
