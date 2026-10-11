# 内部設計書: Task 0 ハング防止・Watchdog即時検知・3時間タイムアウト・HTTPタイムアウト厳格化 (Issue #861)

## 1. 詳細内部仕様

### 1.1 `ParseDetailPageAsyncBase._apply_download_delay_if_needed` (api.py)
```python
# クラス変数定義
_SITE_RATE_LOCKS: ClassVar[dict[str, threading.Lock]] = {}
_SITE_LAST_START_TIMES: ClassVar[dict[str, float]] = {}

async def _apply_download_delay_if_needed(self):
    company = self._resolve_target_company()
    if not company:
        return
    delay = self.SITE_DOWNLOAD_DELAYS.get(company, 0.0)
    if delay <= 0.0:
        return

    # スレッドセーフな初期化
    if company not in self._SITE_RATE_LOCKS:
        with _dispatched_detail_lock:
            if company not in self._SITE_RATE_LOCKS:
                self._SITE_RATE_LOCKS[company] = threading.Lock()

    # threading.Lock による保護区間 (イベントループまたぎ RuntimeError を完全防止)
    sleep_sec = 0.0
    with self._SITE_RATE_LOCKS[company]:
        last_time = self._SITE_LAST_START_TIMES.get(company, 0.0)
        now = time.monotonic()
        elapsed = now - last_time
        if elapsed < delay:
            sleep_sec = delay - elapsed
            self._SITE_LAST_START_TIMES[company] = now + sleep_sec
        else:
            self._SITE_LAST_START_TIMES[company] = now

    if sleep_sec > 0.0:
        await asyncio.sleep(sleep_sec)
```

### 1.2 `ApiAsyncProcBase._handle_local_execution` (api.py)
```python
max_timeout = float(os.getenv("LOCAL_EXECUTION_TIMEOUT_SEC", "120.0"))
start_time = time.monotonic()

t = threading.Thread(target=run_in_new_loop)
t.start()
while t.is_alive():
    t.join(1.0)
    if os.path.exists("stop.flag"):
        logger.info("stop.flag found, forcing exit...")
        from django.db import close_old_connections
        close_old_connections()
        os._exit(0)
    if time.monotonic() - start_time > max_timeout:
        logger.error("Local execution timed out after %.1fs for %s", max_timeout, detail_url)
        return detail_url, 504, "LocalTimeout"
```

### 1.3 `run_all_crawlers.py` (Watchdog ループ)
```python
# 子プロセス投入時の初期タプル (8要素に統一)
now_ts = time.time()
active_processes[idx] = (proc, company, ptype, now_ts, start_dt, now_ts, 0, now_ts)

# 進捗監視ループ
if HANG_THRESHOLD_SEC > 0:
    for idx in tuple(active_processes.keys()):
        if idx not in active_processes:
            continue
        proc, company, ptype, start_t, start_dt, *extra = active_processes[idx]
        last_act = extra[0] if extra else start_t
        prev_db_cnt = extra[1] if len(extra) > 1 else 0
        last_check_t = extra[2] if len(extra) > 2 else 0.0
        if (now - last_check_t) >= 15.0:
            counts = get_count_for_job(company, ptype, start_dt)
            current_db_cnt = counts[2] if counts[0] is not None else None
            if current_db_cnt is not None:
                if current_db_cnt > prev_db_cnt:
                    last_act = now
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
            else:
                active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)
            # break を撤廃し、全アクティブプロセスを走査
```

### 1.4 タイムアウト定義の同期 (3時間 = 10,800秒)
- `terraform/variables.tf`:
  - `crawler_timeout`: default = `"10800s"`, validation: `<= 10800`
- `src/crawler/scripts/ensure_resources_stopped.py`:
  - `DEFAULT_HUNG_THRESHOLD_SEC = 11400.0`
- `src/crawler/scripts/ops/run_all_crawlers.py`:
  - `timeout_sec = int(os.getenv("CRAWLER_TIMEOUT_SEC", "10800"))`
- `src/crawler/scripts/ops/run_pipeline.py`:
  - `DEFAULT_TIMEOUT_SEC: float = 10800.0`
