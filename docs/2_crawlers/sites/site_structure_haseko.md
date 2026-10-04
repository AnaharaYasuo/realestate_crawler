# サイト構造: 長谷工の仲介 (Haseko)

## 概要
- **サイト名:** 長谷工の仲介 (haseko-chukai.com)
- **ベースURL:** `https://www.haseko-chukai.com`
- **タイプ:** 居住用（中古マンション特化）
- **レンダリング方式:** 静的HTML (SSR)

## URLパターン

### 1. スタート・検索結果 (一覧ページ)
- **エリア一覧:** `https://www.haseko-chukai.com/syutoken-buy/mansion/areas/tokyoto/`
- **市区町村一覧:** `https://www.haseko-chukai.com/syutoken-buy/mansion/tokyoto/{city}-city/?page={n}`
- **ページネーション戦略:** `UrlPatternPagination`（`?page={n}`）

### 2. 詳細ページ
- **URLパターン:** `https://www.haseko-chukai.com/detail/{id}/` (例: `/detail/HRA64237/`)

## セレクタ (詳細ページ)

### 共通情報
- **物件名:** `h1` または タイトル先頭
- **価格:** `.price` から正規表現抽出 (`converter.parse_price` で円単位化)
- **スペックマップ:** ページ内の `<dl>` タグを走査し `dt.get_text()` ➔ `dd.get_text()` をキャッシュ

| 項目名 (dt) | モデルフィールド | 抽出・変換ルール |
| :--- | :--- | :--- |
| **物件種別** | `propertyType` | 売マンション (Mansion確定) |
| **所在地** | `address` | 文字列抽出 |
| **交通** | `traffic` | 沿線・駅・徒歩 |
| **専有面積** | `senyuMenseki` | `converter.parse_menseki` |
| **間取り** | `madori` | 文字列抽出 |
| **築年月** | `chikunengetsu` | `converter.parse_chikunengetsu` |
| **構造・階建て** | `kouzou`, `kaisu` | 構造・階数抽出 |
| **管理費** | `kanrihi` | `converter.parse_price` |
| **修繕積立金** | `syuzenTsumitate` | `converter.parse_price` |

### 掲載終了検知
- HTTP 404
- 本文中の「掲載終了」「お探しの物件は見つかりませんでした」検知で `ListingEndedException` 送出。
