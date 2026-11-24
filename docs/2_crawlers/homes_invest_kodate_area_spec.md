# LIFULL HOME'S 投資用一棟物件（invest_kodate）土地面積抽出仕様

## 概要
`HomesInvestmentApartmentParser` において、一棟売りアパート・一棟貸家等の物件詳細ページに `専有面積(最小 - 最大)`（例: `43.06㎡ ～ 43.06㎡`）のような範囲表記が存在する場合でも、区分マンションと誤判定して `tochiMenseki`（土地面積）をクリアしないことを保証する。

## 判定ルール
- `専有面積` / `壁芯面積` テーブルセルに範囲表記（`～` または `〜`）が含まれる場合は、一棟物件の参考情報とみなし、区分マンションオーバーライドのトリガー（`parsed_senyu`）としては扱わない。
- これにより、一棟物件の `tochiMenseki`（土地面積）および `tochiMensekiStr` が欠損せず保持される。

## 会員限定ログインリダイレクトの掲載終了判定（Issue #1794）
- `toushi.homes.co.jp/bukkendetail/index/...` へのアクセスが `マイページログイン`（`/login?redirect=...`）へリダイレクトされた場合、`HomesParser._parsePropertyDetailPage` は一般公開終了（会員限定化）とみなし `ListingEndedException` を送出する。これにより、面積欠損による `SkipPropertyException`（`transient_skipped`）としての無限再クロールを防止する。

## `kodate` → `invest_kodate` 自己切替の継続仕様（Issue #1794）
- `ParserBase._maybe_switch_parser` において、`self.property_type == "kodate"` かつ `detected_type == "invest_kodate"` と判定され、`UrlRouter.create_parser` が正規の担当パーサーとして `self.__class__` 自身を返却した場合（専用投資パーサーを持たない会社）は、`IncompatiblePropertyTypeException` を送出せず現行パーサー（`self`）のまま継続する。

## 関連 Issue
- Issue #1671
- Issue #1794
