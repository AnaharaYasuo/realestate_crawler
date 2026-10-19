# 内部設計書: 独立エグゼキュータの設定と階層スレッド待機の詳細設計 (Issue #1022)

## 1. 独立 ThreadPoolExecutor の設定 (`_getActiveEventLoop` / `run_in_new_loop`)
- `concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="crawler-exec")` を各イベントループ作成時に生成。
- `loop.set_default_executor(executor)` により asyncio のデフォルトエグゼキュータとして設定。
- これにより、Python インタプリタ終了処理時におけるグローバルエグゼキュータの先行シャットダウンの影響を完全に遮断。
- イベントループのクローズ処理時に `executor.shutdown(wait=False, cancel_futures=True)` を実行。

## 2. 階層スレッド待機ロジックの改善 (`_wait_for_active_fire_and_forget_threads`)
- スレッド生成タイミングの隙間（親スレッドが終了し子スレッドが登録されるまでの極小スパン）で `alive=0` と判定されないよう、アクティブスレッドの安定性判定（連続N回以上スレッド数が0であることを確認）またはディスパッチ中の登録管理を徹底。
- 待機ループ内で `stop.flag` を検知可能とし、SIGINT / SIGTERM での即座終了に対応。
- タイムアウトは環境変数 `CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT` を参照（デフォルト 7200 秒）。
