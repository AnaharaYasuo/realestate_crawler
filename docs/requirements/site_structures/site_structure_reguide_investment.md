# サイト構造: RE-Guide（リガイド収益物件）

## 概要
- **サイト名:** RE-Guide収益物件 (リガイド)
- **ベースURL:** `https://re-guide.jp/investment/`
- **タイプ:** 投資用不動産 (投資用マンション(区分), 一棟アパート, 一棟マンション, 一棟ビル 等)

## URLパターン

### 1. 検索結果 (一覧ページ)
- **URL例:** `https://re-guide.jp/investment/list/?search_kind=area&pref=13&i_type=101&_enc=EUC-JP`
  - `pref`: 都道府県コード (13: 東京都, 14: 神奈川県, 11: 埼玉県, 12: 千葉県 等)
  - `i_type`: 物件種別コード (101: 投資用マンション(区分), 202: 一棟アパート 等)
  - `page`: ページネーション (`&page=2`)

#### 一覧ページ要素抽出
- **物件リストコンテナ:** `ul#result_list > li`
- **詳細URLセレクタ:** `li a[href^="/investment/"][href$="/"]`（例: `/investment/421139/`）

### 2. 詳細ページ
- **URL:** `https://re-guide.jp/investment/{estate_id}/`

## セレクタ・テーブル構造 (詳細ページ)
`InvestmentParserBase` に対応するフィールドマッピング。

| 項目名 (th / td) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **物件名** | `propertyName` | `title` タグまたはテーブル「物件名」 |
| **価格** | `price`, `priceStr` | テーブル「価格(税込)」 |
| **満室想定年間収入** | `annualRent` | テーブル「満室想定年間収入」 |
| **想定表面利回り** | `grossYield` | テーブル「満室想定表面利回り」または「利回り」 |
| **所在地** | `address`, `address1`, `address2`, `address3` | テーブル「所在地」 |
| **交通** | `traffic1`, `station1`, `walkMinutes1` | テーブル「交通」 |
| **専有面積** | `senyuMenseki`, `senyuMensekiStr` | テーブル「専有面積」 |
| **間取り** | `madori` | テーブル「間取り」 |
| **築年月** | `chikunengetsu`, `chikunengetsuStr` | テーブル「築年月」 |
| **構造** | `kouzou` | テーブル「構造」 |
| **階数 / 所在階** | `kaisu`, `shozaikai` | テーブル「階数」 |
| **現況** | `genkyo` | テーブル「現況」 |
| **総戸数** | `soukosu` | テーブル「総戸数」 |
| **土地権利** | `tochikenri` | テーブル「土地権利」 |
| **管理費** | `kanrihi` | テーブル「管理費/月」 |
| **修繕積立金** | `shuzenTsumitatekin` | テーブル「修繕積立金/月」 |
| **取引態様** | `torihiki` | テーブル「取引態様」 |
| **引渡時期** | `hikiwatashi` | テーブル「引渡時期」 |
| **備考** | `biko` | テーブル「備考」 |
