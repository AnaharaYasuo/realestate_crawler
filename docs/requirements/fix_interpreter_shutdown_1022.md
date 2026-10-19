# 要件定義書: クローラー巡回中のインタプリタシャットダウン防止と独立エグゼキュータによる堅牢化 (Issue #1022)

## 1. 背景・課題
- Issue #1011 にて全サイトのスタート〜一覧〜詳細クローラー巡回を Fire-and-Forget (即時 HTTP 202 レスポンスによるバックグラウンド並行実行) 化した。
- しかし、CLI (`main.py`) またはバッチ実行において、ルートの `main()` が完了した直後に `_wait_for_active_fire_and_forget_threads` がデフォルトの300秒タイムアウト、またはスレッド生成タイミング差による `alive=0` 判定で終了してしまうケースがある。
- ルート `main()` の終了によって `main.py` プロセスが `sys.exit(0)` またはスクリプト終端に到達すると、Python インタプリタのシャットダウン処理が開始される。
- Python インタプリタシャットダウン中はデフォルトの `ThreadPoolExecutor` が閉鎖されるため、バックグラウンドデーモンスレッド上で動作している aiohttp の DNS 解決（`loop.getaddrinfo()` ➔ `loop.run_in_executor(None, ...)`）が `RuntimeError: cannot schedule new futures after interpreter shutdown` でクラッシュする。

## 2. 目的・要件
1. **プロセス早期終了の防止 (待機タイムアウトの適正化・無限待機/十分な猶予)**:
   - CLI / 単体実行時、子・孫のバックグラウンドタスクがすべて処理を終えるまでルート待機が継続すること。
   - バックグラウンドスレッドが次のスレッド（例: start ➔ region ➔ area ➔ list ➔ detail）を生成している間の一時的な `alive=0` による早期離脱を防止する。
   - 待機タイムアウト値は環境変数 `CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT` で制御可能とし、デフォルトは巡回が十分完了できる長大時間（例: 7200秒 = 2時間）または `0` で完全待機とする。
2. **各イベントループの独立 ThreadPoolExecutor 保持**:
   - `ApiAsyncProcBase` のイベントループ (`_getActiveEventLoop` または `run_in_new_loop`) において、Python のグローバルデフォルトエグゼキュータに依存せず、各ループ専用の明示的な `concurrent.futures.ThreadPoolExecutor` を作成して `loop.set_default_executor(executor)` に設定する。
   - これにより、たとえメインスレッドや外部要因でインタプリタのシャットダウンがトリガーされかけた場合でも、aiohttp の DNS 解決等の内部 Executor 呼び出しが閉鎖済みグローバルエグゼキュータでクラッシュすることを防御する。
   - ループ終了時に専用エグゼキュータを安全にシャットダウン（`executor.shutdown(wait=False, cancel_futures=True)`）する。
