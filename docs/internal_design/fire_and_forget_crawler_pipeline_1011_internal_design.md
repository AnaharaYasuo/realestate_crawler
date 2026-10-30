# 内部設計書: 全サイト巡回パイプラインの非同期投げっぱなし（Fire-and-Forget）化

## 1. モジュール変更詳細

### 1.1 `src/crawler/package/api/api.py`

#### `_handle_local_execution(self, api_url, detail_url)`
```python
# 環境変数フラグの判定
fire_and_forget = os.getenv("CRAWLER_FIRE_AND_FORGET", "true").lower() in ("true", "1")

# スレッド起動
t = threading.Thread(target=run_in_new_loop, daemon=True)
t.start()

if fire_and_forget:
    # スレッドが生存している（起動成功した）ことを確認して即時復帰
    logger.info("Fire and forget (local dispatch): %s -> %s", path, detail_url)
    return detail_url, 200, "FireAndForgetLocal"

# CRAWLER_FIRE_AND_FORGET=false の場合は従来の同期待機ロジック
max_timeout = float(os.getenv("LOCAL_EXECUTION_TIMEOUT_SEC", "120.0"))
timeout_res = self._wait_for_local_execution(t, max_timeout, detail_url)
if timeout_res is not None:
    return timeout_res

if child_errors:
    logger.error("Local execution failed for %s: %r", detail_url, child_errors[0])
    return detail_url, 500, "LocalError"
return detail_url, 200, "LocalSync"
```

#### スレッド内の例外ハンドリングとリソース回収
`run_in_new_loop` 内の `finally` 句において、例外発生の有無にかかわらず以下を徹底：
1. `_crawl_run_state.keys` のリセット
2. Django DB コネクションの完全解放 (`close_old_connections()`, `connections.close_all()`)
3. イベントループのクローズ (`new_loop.close()`)
4. 予期しない例外発生時はログ（`logger.exception`）に出力し、プロセス全体への影響を局所化。

## 2. テスト設計

### 2.1 単体テスト `test_fire_and_forget_pipeline.py`
1. **Fire-and-Forget 有効時の検証**:
   - `CRAWLER_FIRE_AND_FORGET="true"`
   - モックされた `TargetClass.main` に意図的に 5秒の `time.sleep` を挟む。
   - `_handle_local_execution` を実行した際、5秒待たずに即座（0.1秒未満）に `(url, 200, "FireAndForgetLocal")` が返されることを検証。
2. **同期モード（後方互換）の検証**:
   - `CRAWLER_FIRE_AND_FORGET="false"`
   - スレッドが完了するまで待機し、`200 "LocalSync"` が返されることを検証。
3. **タイムアウト挙動の検証**:
   - `CRAWLER_FIRE_AND_FORGET="false"` かつ `LOCAL_EXECUTION_TIMEOUT_SEC=0.2`
   - スレッドが完了しない場合に `504 "LocalTimeout"` が返されることを検証。
