# ServerBusyException (HTTP 503) 即時中断仕様 (#1696)

## 概要
詳細ページ取得ワーカー（`ParseDetailPageAsyncBase`）および健美家 `curl_cffi` レスポンスハンドラ（`KenbiyaParserBase._handle_curl_cffi_response`）において、HTTP 500/502/503/504 等のサーバー過負荷・WAF ブロック検知時に残余の fire-and-forget ワーカーを即時中断する。

## 仕様
1. `KenbiyaParserBase._handle_curl_cffi_response` は HTTP `500, 502, 503, 504` で `ServerBusyException` を送出する。
2. `ParseDetailPageAsyncBase._classify_fetch_exception` は `ServerBusyException` 検知時に `_server_busy_abort_event` をセットする。
3. 後続ワーカーの `_execute_single_detail_fetch` および `_wait_for_active_fire_and_forget_threads` は `_server_busy_abort_event.is_set()` を検知して即座に中断・未実行タスクをキャンセルする。
