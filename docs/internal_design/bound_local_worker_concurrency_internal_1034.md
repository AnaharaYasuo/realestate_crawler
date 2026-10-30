# ローカルバックグラウンドワーカー多重度制限 内部設計書 (Issue #1034)

## 1. モジュール設計
`src/crawler/package/api/api.py`:
- `_get_local_worker_semaphore()`:
  - グローバルな `threading.Semaphore` を提供。
  - 初期値は `int(os.getenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "20"))`。
- `_handle_local_execution()`:
  - スレッド内部（`run_in_new_loop`）で `_get_local_worker_semaphore().acquire()` してからイベントループを生成・実行する、あるいは `ThreadPoolExecutor(max_workers=...)` でタスクをキューイングする。
  - 最も安定かつ既存の `_track_fire_and_forget_thread` / `Thread` 管理と親和性が高いのは、**`ThreadPoolExecutor` によるタスク管理**、または **スレッド起動前の `threading.Semaphore` 制御**。
  - ただし「一覧ページ側のイベントループをブロックさせない非同期制御」のため、一覧処理からディスパッチする際にセマフォ枠（またはキュー）で実行待ちを行い、OSスレッド自体の実体生成数を上限20に抑え込む。

```python
_local_worker_semaphore = None
_local_worker_semaphore_lock = threading.Lock()

def _get_local_worker_semaphore() -> threading.Semaphore:
    global _local_worker_semaphore
    with _local_worker_semaphore_lock:
        if _local_worker_semaphore is None:
            limit = int(os.getenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "20"))
            _local_worker_semaphore = threading.Semaphore(limit)
        return _local_worker_semaphore
```

`_handle_local_execution` 内でのフロー:
- `_get_local_worker_semaphore().acquire()` をスレッド起動前に行うと、一覧の同期処理がブロックされる場合があるため、スレッド内部の最初で acquire し、finally で release する形をとる。
- ただし「スレッドオブジェクト自体のスタックメモリ確保」を防ぐため、`ThreadPoolExecutor`（固定スレッド数20）にタスク関数を投入する。
- 投入された `Future` を追跡し、`_wait_for_active_fire_and_forget_threads` で全 Future の完了を待機する。
