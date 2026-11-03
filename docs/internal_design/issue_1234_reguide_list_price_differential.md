# 仕様書: リガイド（reguide - investment）一覧ページ価格抽出と価格差分スキップの有効化 (Issue #1234)

## 1. 概要
リガイド投資用物件クローラー（`reguide - investment`）において、一覧ページ（`ul#result_list > li`）上に物件価格が明記されているにもかかわらず、一覧解析メソッド `parseRootPage` が URL のみ（`ListItem(url=url)`）を返していたため、差分クローリングエンジン（`differential.py`）における価格変更検知（価格据え置き時のスキップ、および価格改定時の即時再取得）が機能していなかった。
本改修では、一覧ページの各カードから物件URLと価格を抽出し、`ListItem(url=url, price=price)` を返すようパーサーを改修する。

## 2. 変更仕様

### 2.1 パーサー改修 (`src/crawler/package/parser/reguideParser.py`)
- `parseRootPage(self, response: BeautifulSoup)`:
  - 一覧カード `ul#result_list > li` を走査。
  - 詳細URL: `a[href*='/investment/']` から抽出（正規表現 `^/investment/(?:\d+|detail/id/[^/]+)/?` にマッチするもの）。
  - 価格: `table.price` の `td` またはカード内の価格表記文字列から抽出し、`converter.parse_price(price_str)` を用いて数値化（万単位/円単位対応）。
  - 各カードにつき `ListItem(url=abs_url, price=price)` を yield。
  - 万が一 `ul#result_list > li` が取得できない構造の場合は、既存の `extract_detail_urls` をフォールバックとして `ListItem(url=url, price=None)` を返す。

### 2.2 単体テスト追加 (`src/crawler/tests/unit/test_reguide_list_price.py`)
- 一覧ページのHTMLモック（カード内にURLと価格「3億5,800万円」「1,280万円」が含まれる）を用意し、`parseRootPage` が正確に URL と価格（358000000, 12800000 等）を保持した `ListItem` を返すことを検証。
- 価格が記載されていないカードの場合でもエラーとならず `price=None` で安全にフォールバックすることを確認。

## 3. 受入基準 (Acceptance Criteria)
1. `parseRootPage` が各カードから詳細URLと抽出価格（`int` または `Decimal`）を含む `ListItem` を yield すること。
2. 差分クローラーにより、価格据え置き時は詳細取得がスキップされ、価格変更時は再取得されること。
3. すべての単体テストおよびアーキテクチャハーネス（`test_architecture_harness.py`）に合格すること。
