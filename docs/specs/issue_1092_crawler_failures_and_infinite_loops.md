# Issue #1092: クローラー異常修復仕様書 (misawa無限ループ、ietanドメイン/SSL、長谷工ドメイン移転、およびTohoHouseドメイン修正)

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
3. **toho（東宝ハウス）ドメインおよび一覧リンク・ページネーション修正**:
   - `toho-house.media` のDNSレコードが存在しないため即座に失敗していた。
   - 初期設計書（`site_structure_toho.md`）の正規ドメイン `https://th-yokohama.com` に修正し、一覧カードのリンク正規表現（`estate_detail_\d+`）およびページネーション（`.propertyPager__nextLink`）を対応。
4. **haseko（長谷工）正規ドメインへの修正**:
   - 旧ドメイン `www.haseko-urbannet.co.jp` から正規ドメイン `https://www.haseko-chukai.com` に更新。
   - サイトが緊急メンテナンス（HTTP 503）中の場合は `baseParser` の `ServerBusyException` により安全にスキップ（Exit Code 0）される仕様を担保。

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
- **toho**:
  - `TohoBaseParser.BASE_URL = "https://th-yokohama.com"`
  - `parsePropertyListPage`: `(?:/detail/|estate_detail_)[a-zA-Z0-9_-]+` にマッチするリンクを抽出
  - `parseNextPage`: `.propertyPager__nextLink` を優先取得
  - `mid_brokers_routes.py`:
    - mansion: `https://th-yokohama.com/estates/index?div=1&page=1`
    - kodate: `https://th-yokohama.com/estates/index?div=2&page=1`
    - tochi: `https://th-yokohama.com/estates/index?div=0&page=1`
- **haseko**:
  - `HasekoMansionParser.BASE_URL = "https://www.haseko-chukai.com"`
  - `mid_brokers_routes.py`: `https://www.haseko-chukai.com/syutoken-buy/mansion/areas/tokyoto/`

## 3. テスト計画
- `test_misawa_parser.py`:
  - 検索結果が空（`<div class="searchList"></div>`、かつ `li.next a` が存在）のHTMLを渡したとき、`parseNextPage` が `""` を返し、無限ループしないことをアサート。
- `test_mid_broker_parsers.py`:
  - ietan, toho, haseko の各パーサーおよび詳細ページ・掲載終了判定が正常動作することを確認。
- `test_toho_list_and_next_page.py`:
  - toho の一覧カード抽出および次ページURL取得が正しく動作することを確認。

