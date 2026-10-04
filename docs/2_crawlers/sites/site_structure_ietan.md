# サイト構造: 大成有楽不動産販売 (ietan)

## 概要
- **サイト名:** 大成有楽不動産販売 (ietan.jp)
- **ベースURL:** `https://www.ietan.jp`
- **タイプ:** 居住用（中古マンション, 戸建, 土地）
- **レンダリング方式:** 静的HTML (SSR)

## URLパターン

### 1. スタート・検索結果 (一覧ページ)
- **中古マンション:** `https://www.ietan.jp/mansion/tokyo/list/c_{code}?page={n}`
- **戸建て:** `https://www.ietan.jp/kodate/tokyo/list/c_{code}?page={n}`
- **土地:** `https://www.ietan.jp/tochi/tokyo/list/c_{code}?page={n}`
- **ページネーション戦略:** `UrlPatternPagination`（`?page={n}`）

### 2. 詳細ページ
- **中古マンション:** `https://www.ietan.jp/mansion/detail/{id}` (例: `MHF95987`)
- **戸建て:** `https://www.ietan.jp/kodate/detail/{id}`
- **土地:** `https://www.ietan.jp/tochi/detail/{id}`

## セレクタ (詳細ページ)

### 共通情報
- **物件名:** `h1` または `section.estateProfile dl.dataBlock` の `物件名`
- **価格:** `.price` (正規表現で円単位整数化)
- **スペックマップ:** `section.estateProfile` 配下の `<dt>` と `<dd>` を1対1で抽出・キャッシュ

| 項目名 (dt) | モデルフィールド | 抽出・変換ルール |
| :--- | :--- | :--- |
| **所在地** | `address` | 文字列抽出 |
| **交通** | `traffic` | 駅徒歩分数 |
| **専有面積** | `senyuMenseki` | `converter.parse_menseki` |
| **間取り** | `madori` | 文字列抽出 (例: 2LDK) |
| **築年月** | `chikunengetsu` | `converter.parse_chikunengetsu` (例: 1999年01月) |
| **構造・階建** | `kouzou`, `kaisu` | 構造(SRC等)と所在階/総階数へ分割 |
| **管理費** | `kanrihi` | `converter.parse_price` |
| **修繕積立金** | `syuzenTsumitate` | `converter.parse_price` |
| **土地権利** | `tochikenri` | 文字列 (所有権等) |

### 掲載終了検知
- HTTP 404
- 本文中の「お探しの物件は見つかりませんでした」「掲載を終了いたしました」検知で `ListingEndedException` 送出。
