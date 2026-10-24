# Issue #1092: クローラー異常修復仕様書 (misawa無限ループ、ietanドメイン/SSL、長谷工ドメイン移転、およびWatchdog進捗更新)

## 1. 概要
直近12時間のSlackアラート監視（#property_alert / #dev-agent）により判明した以下のシステム・クローラー不具合を解消する。
1. **misawa（ミサワホーム）無限ループバグの解消**:
   - 検索結果が0件（`<div class="searchList">` が空）であっても、ミサワホーム側HTMLの不具合により `<li class="next"><a href="...&page=N"></a></li>` が常時出力される。
   - これによりパーサーが無限に次ページを巡回し続け、タイムアウト上限（2時間）まで実行を浪費して0件失敗していた。
   - **対策**: `parsePropertyListPage` で取得した物件数が0件の場合、または一覧内に有効な物件カードが存在しない場合は、`parseNextPage` で次ページを探索せず即座に打ち切る（空文字列を返す）。
2. **ietan（大成有楽）ドメインおよびSSL証明書エラーの修正**:
   - `BASE_URL` が `https://ietan.jp`（Apexドメイン）になっており、SSL証明書のコモンネーム（`www.ietan.jp` / `*.ietan.jp`）と不一致を起こして `SSLCertVerificationError` で即座に失敗（Exit Code 1）していた。
   - また、土地の初期URLが `/tochi/tokyo/`（HTTP 404）となっていた。正しくは `/land/tokyo`。
   - **対策**: `BASE_URL` を `https://www.ietan.jp` に修正し、`routes/mid_brokers_routes.py` 内の初期URLも `https://www.ietan.jp/mansion/tokyo`、`https://www.ietan.jp/kodate/tokyo`、`https://www.ietan.jp/land/tokyo` に統一する。
3. **toho / haseko 等のドメイン失効・移転に伴う安全なエラーハンドリング / スキップ**:
   - 旧ドメイン（`toho-house.media`, `haseko-urbannet.co.jp`）のDNS失効によるクラッシュに対し、DNS未解決時やドメイン移転時はわかりやすいログを残し、パイプライン全体を停止させない。

## 2. 外部設計
- **misawa**:
  - `MisawaParser.parseNextPage`:
    - 当該ページ（response）の `div.searchList` 内に物件セクション（`div.section` や `a[href*="detail_"]` 等）が1件も存在しない場合、または検索結果が0件である場合は、次ページが存在しても以降のページをたどらず `""` を返却する。
- **ietan**:
  - `IetanBaseParser.BASE_URL = "https://www.ietan.jp"`
  - `mid_brokers_routes.py`:
    - mansion: `https://www.ietan.jp/mansion/tokyo`
    - kodate: `https://www.ietan.jp/kodate/tokyo`
    - tochi: `https://www.ietan.jp/land/tokyo`

## 3. テスト計画
- `test_misawa_parser.py`:
  - 検索結果が空（`<div class="searchList"></div>`、かつ `li.next a` が存在）のHTMLを渡したとき、`parseNextPage` が `""` を返し、無限ループしないことをアサート。
- `test_mid_broker_parsers.py`:
  - ietanのURLがすべて `https://www.ietan.jp` になっていること、および土地URLが `/land/` を向いていることをテスト。
