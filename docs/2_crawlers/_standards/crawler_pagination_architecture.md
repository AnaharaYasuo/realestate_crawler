# クローラー巡回・ページネーション標準アーキテクチャ (Crawler & Pagination Architecture)

## 1. 概要と背景
各サイトのパーサー（HTML詳細パース）が `ParserBase` で統一されているのに対し、一覧ページの巡回・ページ送り（ページネーション）ロジックがサイトごとにアドホックに実装される問題を解決するため、本共通アーキテクチャを策定する。

新規サイト追加時は、本仕様で定義された `PaginationStrategy` を選択・継承して実装しなければならない。

---

## 2. ページネーション戦略 (PaginationStrategy) の分類

サイトの特性に応じて、以下の4つの標準パターンのいずれかを選択して実装する。

| パターン名 | 対象サイトの特性 | 実装クラス / アプローチ | 主なパラメータ・判定 |
| :--- | :--- | :--- | :--- |
| **`UrlPatternPagination`** | URLのパスやクエリでページ番号・オフセットが規則的に変化するサイト | `page_param: str`<br>`page_format: str` | `?page={n}`, `/page/{n}/`, `?offset={n*limit}`<br>最終ページ判定: 取得件数0件、または最大ページ超過 |
| **`NextLinkPagination`** | ページ番号がURLから推測できず、HTML内の「次へ」リンクを辿る必要があるサイト | `selector: str` | `a.next`, `link[rel="next"]`<br>次リンクの `href` を抽出し相対/絶対URLを解決。存在しない場合終了 |
| **`CursorAjaxPagination`** | 一覧が非同期API/JSONで返り、レスポンス内の `next_cursor` や `last_id` を渡すサイト | `cursor_key: str`<br>`request_type: GET/POST` | レスポンスJSON内のカーソルトークンを次回リクエストヘッダー/ボディに設定 |
| **`PlaywrightScrollPagination`** | 無限スクロールや動的ボタンクリック（「もっと見る」）が必要な動的SPAサイト | `click_selector: str`<br>`scroll_delay: float` | 画面最下部へのスクロール実行 ➔ 要素追加待機 ➔ 新規要素0件で終了判定 |

---

## 3. クローラーの責務境界 (Crawler vs Parser)

システム全体の安定性と責務分離のため、クローラーエンジンとパーサーの責任境界を以下のように厳格化する。

```
[ クローラー (Crawler Engine) ]
  ├── 1. シードURL管理・エリア分割
  ├── 2. レートリミット（間隔制御 1.0s〜2.0s）＆ サーキットブレイカー（連続3回失敗即停止）
  ├── 3. ページネーション制御 (PaginationStrategy)
  ├── 4. 一覧スニペットの事前フィルタリング (ListSnippetParser による対象外の事前間引き)
  └── 5. 詳細ページ取得キューへの投入
         ↓
[ パーサー (Parser Engine) ]
  ├── 1. DOMパースと specs キャッシュ化
  ├── 2. 生文字列の抽出 (get_<field>_str)
  └── 3. 正規化エンジンへの引き渡し (DataNormalizer)
```

---

## 4. 2段階パース（事前間引き）プロトコル

詳細ページへの不要なHTTPリクエストやPlaywright実行を削減し、トラフィックと実行時間を最小化するため、すべてのクローラーは一覧スニペットでの事前検証をサポートする。

1. **`ListSnippetParser.filter_candidate(snippet_element) -> bool`**:
   - 一覧の時点で「対象外種別（例: 投資用収集時における区分マンション）」、「成約済/商談中」、「対象外エリア」と判別できる物件は詳細リクエストを行わずにスキップする。
2. **スニペットメタデータの一時保持**:
   - 一覧ページにしか記載されていないメタ情報（「新着日時」「掲載開始日」「担当店舗」など）は辞書として保持し、詳細ページのパース結果とマージしてDB永続化層へ渡す。


---

## 5. サイト別シードURL・全国走査・ページネーション不変条件

取得件数が極端に少ない（1ページ止まり・特定市区町村限定・トップページのみ参照）状態を防止するため、各クローラーのスタートURLおよび `parseNextPage` は以下の不変条件を満たさなければならない。

1. **京成不動産 (`keisei`)**:
   - **スタートURL**: マンション (`r_type=3`)・戸建 (`r_type=2`)・土地 (`r_type=1`) すべてにおいて、特定区フィルタ (`pl_13[]`) を含まない全国一覧URL (`/contents/code/search_result?mode=list&all_pref=1&r_type={1|2|3}&by=area`) を使用する。
   - **ページネーション**: `parseNextPage(response, current_url)` にて `value` に `"次"` を含む `<input onClick="form1_submit('N')">`（または `<select name="offset">` の次オプション）から1始まりのページ番号 `offset` を抽出し、`current_url` のクエリパラメータ `offset` を更新して全ページを巡回する（「前10件」ボタンの `form1_submit` による無限ループを防止すること）。
2. **東京建物不動産販売 (`totate`)**:
   - **スタートURL**: 特定市区町村パラメータ (`city[]=13112` 等) や地域パス (`/kanto/` 等) を付与せず、全国全件を100件単位で返す `/buy/search/result/detail_search/{property_type}/?limit=100` を使用する。
   - **ページネーション**: `.paging a, .pager a` 内の「次」リンクの `data-href`（Base64エンコードされた `?page=N&sort=new_arrival&limit=100`）をデコードし、`current_url` のパスに対して結合して最終ページまで巡回する。
3. **住友林業ホームサービス (`sumirin`)**:
   - **スタートURL**: 新着12件のみを表示する種別トップページ (`/buy/{mansion|house|land}/`) ではなく、全国 (`r_seq=9`)・種別 (`ed_cd=01`: マンション, `02`: 戸建, `03`: 土地)・1ページ100件 (`p_num=100`) の検索結果一覧 `/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd={01|02|03}&s_mode=3&f_word=&p_num=100` を使用する。
   - **ページネーション**: `li.next a` 等の次ページリンク (`&p=2`, `&p=3`, ...) を辿り最終ページまで巡回する。
