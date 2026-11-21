# ServerBusyException (HTTP 503) 即時中断仕様 (#1696)

## 概要
詳細ページ取得ワーカー（`ParseDetailPageAsyncBase`）および健美家 `curl_cffi` レスポンスハンドラ（`KenbiyaParserBase._handle_curl_cffi_response`）において、HTTP 500/502/503/504 等のサーバー過負荷・WAF ブロック検知時に残余の fire-and-forget ワーカーを即時中断する。

## 仕様
1. `KenbiyaParserBase._handle_curl_cffi_response` は HTTP `500, 502, 503, 504` で `ServerBusyException` を送出する。
2. `ParseDetailPageAsyncBase._classify_fetch_exception` は `ServerBusyException` 検知時に `_server_busy_abort_event` をセットする。
3. 後続ワーカーの `_execute_single_detail_fetch` および `_wait_for_active_fire_and_forget_threads` は `_server_busy_abort_event.is_set()` を検知して即座に中断・未実行タスクをキャンセルする。


---

## 詳細ページフェッチ・サーキットブレーカー (`DetailFetchCircuitBreaker`) [#1708]

- **目的**: 一覧ディスパッチ完了後に詳細ページワーカーで `SkipPropertyException`（HTTP 503 等）が連続発生した際、残りのワーカーキューが空回りしてリクエストを投げ続けるのを防止し、即座に処理を打ち切る。
- **動作仕様**:
  - ホスト単位で連続 `SkipPropertyException` 発生回数をカウントし、しきい値（`DETAIL_CIRCUIT_BREAKER_THRESHOLD`、デフォルト `10` 回）に達するとサーキットを `OPEN` 状態にする。
  - 正常取得（`item is not None`）時は連続カウントをリセットする。
  - `OPEN` 状態の間は `_execute_single_detail_fetch()` の先頭で即座に `None` を返却し、ネットワークアクセスを行わずにワーカースレッドを終了させる。
- **健美家詳細ページ並列数**:
  - `KENBIYA_DETAIL_PARALLEL_LIMIT`（デフォルト `5`）により、レート制限時間枠内での処理スループットを向上させる。


---

## 60分稼働→15分休止 自動クールダウン制御 (`CrawlCooldownController`) [#1712]

- **目的**: 健美家など約 70 分で HTTP 503 レート制限に達するサイトに対し、60 分（3600 秒）稼働ごとに 15 分（900 秒）の自動休止を挟むことで、503 を踏まずに全件クロールを完走させる。
- **動作仕様**:
  - `CrawlCooldownController` がホスト単位で稼働開始時刻（`window_start`）と休止終了時刻（`cooldown_until`）をスレッドセーフに管理する。
  - `work_seconds`（健美家デフォルト: `3600` 秒）経過すると、`rest_seconds`（健美家デフォルト: `900` 秒）の休止ウィンドウに入る。
  - 詳細ページワーカーは `_execute_single_detail_fetch()` で休止終了時刻まで `await asyncio.sleep(...)` で待機し、休止明けに稼働ウィンドウをリセットして処理を再開する。
