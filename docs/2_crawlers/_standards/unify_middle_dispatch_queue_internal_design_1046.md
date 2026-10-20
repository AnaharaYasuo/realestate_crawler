# Issue #1046: 中間・エリアページディスパッチのasyncio.Queueワーカープール化内部設計書

## 1. 現状のアーキテクチャの課題
現状の `_handle_local_execution`（`src/crawler/package/api/api.py`）:
```python
# 現状の問題コード
def _handle_local_execution(self, api_url, detail_url):
    ...
    # 呼び出しごとに毎回スレッドを生成
    t = threading.Thread(target=run_in_new_loop, daemon=True)
    _track_fire_and_forget_thread(t)
    t.start()
    if fire_and_forget:
        return detail_url, 202, "FireAndForgetLocal"
```
- この実装では、`sem` による実行数の制御は行っているものの、**OSスレッド `threading.Thread` そのものが無制限に作られ、数千スレッドが `with sem:` の前で待機**する。
- OSスレッドが1,400本以上作られること自体がメモリ浪費とGILスイッチ競合を招く。

## 2. 改善アーキテクチャ設計
詳細ページ（`_detail_queue` + `_detail_worker`）と同様に、プロセス単位のディスパッチエグゼキュータプール（または固定キューワーカー）を用いる。

### 設計詳細
1. **固定スレッドプール（ThreadPoolExecutor）の導入**:
   - `_get_local_worker_executor()`: `_get_local_worker_concurrency()`（10並行）で初期化されたグローバル固定 `ThreadPoolExecutor` を使用。
   - `t = threading.Thread(...)` の直接生成を撤廃し、`executor.submit(run_task, ...)` で投入。
   - スレッド総数は常に最大10本（設定値）に固定され、OSスレッド乱立（1,400本等）が物理的に発生しなくなる。
2. **フューチャーの追跡・待ち合わせ**:
   - `_track_fire_and_forget_future(fut)` により、`_wait_for_active_fire_and_forget_threads` での安全な完了待ち合わせを保証。
3. **`asyncio` との整合性**:
   - 詳細ページはすでに `_detail_queue` で単一ループ消化されている。中間ページも固定ワーカープールに投入されることで、GIL競合ゼロ・スレッド数極小で整然と消化される。
