# Issue #1602: mitsuiParser 一覧ページ価格抽出およびスマート差分スキップ仕様書

## 1. 概要 (Overview)
`mitsuiParser.py` の `parsePropertyListPage` はすでに `baseParser._parsePageCore` を呼び出すことで `ListItem(url, price)` 形式を返却できる設計となっているが、単体テストによる検証および仕様の明文化が未実施だった。
本仕様書では、三井のリハウス（mitsui）各物件種別において一覧カードから価格（円）を抽出し、`ListItem(url, price)` として返却・差分スキップを機能させる契約を定義する。

## 2. 動作仕様
- `parsePropertyListPage(response)` は `ListItem` インスタンス（`url: str`, `price: int | None`）を yield する。
- 一覧カード内に「3,480万円」「1億2,000万円」等の価格表記が存在する場合、基底クラス `_extract_card_price` により整数（円）へ正規化され `item.price` に格納される。
- これにより `differential.py` が DB 内の最新価格と照合し、価格据え置きの既存物件について詳細ページクロールを安全にスキップする。
