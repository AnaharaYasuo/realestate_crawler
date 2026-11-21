# ServerBusyException (HTTP 503) 即時中断仕様 (#1696)

## 概要
詳細ページ取得ワーカー（`ParseDetailPageAsyncBase`）および健美家 `curl_cffi` レスポンスハンドラ（`KenbiyaParserBase._handle_curl_cffi_response`）において、HTTP 500/502/503/504 等のサーバー過負荷・WAF ブロック検知時に残余の fire-and-forget ワーカーを即時中断する。

## 仕様
1. `KenbiyaParserBase._handle_curl_cffi_response` は HTTP `500, 502, 503, 504` で `ServerBusyException` を送出する。
2. `ParseDetailPageAsyncBase._classify_fetch_exception` は `ServerBusyException` 検知時に `_server_busy_abort_event` をセットする（`src/crawler/package/api/api.py` にて `package.parser.baseParser.ServerBusyException` を明示的にインポートすること [#1714]）。
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

## 60分稼働→30分休止（PPPoE再接続・Cookie再取得）自動クールダウン制御 (`CrawlCooldownController`) [#1712]

- **目的**: 健美家など約 70 分で HTTP 429/503 レート制限に達するサイトに対し、60 分（3600 秒）稼働または 429/503 検知時に即座に一時停止し、PPPoE 切断 → 30 分（1800 秒）待機 → PPPoE 再接続 → Cookie 再取得を行ってから、積んでいる詳細ページ URL キューを維持したまま中断地点から再開する。
- **動作仕様**:
  - `CrawlCooldownController` がホスト単位で稼働開始時刻（`window_start`）と休止終了時刻（`cooldown_until`）をスレッドセーフに管理する。
  - `work_seconds`（健美家デフォルト: `3600` 秒）経過、または `trigger_cooldown()`（HTTP 429/503 検知時）が呼ばれると、`rest_seconds`（健美家デフォルト: `1800` 秒）の休止ウィンドウに入る。
  - 休止開始時に `ifdown wan_pppoe` を実行し、休止終了時に `ifup wan_pppoe` とトップページアクセスによる Cookie 再取得を実行する（各 1 回のみ排他実行）。
  - 詳細ページワーカーは `_execute_single_detail_fetch()` で休止終了時刻まで `await asyncio.sleep(...)` で待機し、休止明けに再取得した Cookie を付与して処理を再開する。


## 東宝ハウス タイトル末尾ブランド文言除去 (#1726)
- `PropertyTypeDetector._strip_title_site_suffix` にて、2番目以降の `｜` セグメントに「不動産なら」「東宝ハウス」を含むサイト共通ブランド文言を除去し、マンション物件が `kodate` と誤判定されるのを防止する。


## MizuhoBypass Playwright タイムアウト対策 (#1730)
- `mizuho_bypass.py` の `get_mizuho_page_html` において、`page.goto` の `wait_until` を `"networkidle"` から `"domcontentloaded"` へ変更し、バックグラウンド通信による 20秒タイムアウトを防止する。


## 東急リバブル 投資用物件ルーティング・種別切替ガード (#1735)
- `UrlRouter` に `invest_kodate` 用の `TokyuInvestmentKodateParser`（`TokyuInvestmentKodate`）を登録し、`/kodate/` 等の投資戸建判定時に `IncompatiblePropertyTypeException` でスキップされるのを防止する。
- `ParserBase._maybe_switch_parser` において、URL に `/fudosan-toushi/` を含む場合は `mansion` へのパーサー切替を抑止し、`TokyuInvestmentApartmentParser` のまま処理を継続する。
