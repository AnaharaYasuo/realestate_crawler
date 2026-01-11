# サイト構造: 三井のリハウス (居住用)

## 概要
- **サイト名:** 三井のリハウス (rehouse.co.jp)
- **ベースURL:** `https://www.rehouse.co.jp`
- **タイプ:** 居住用（中古マンション, 一戸建て, 土地）

## URLパターン

### 1. 検索結果 (一覧ページ)
- **中古マンション (エリア別):** `https://www.rehouse.co.jp/mansion/[AREA_CODE]/`
    - 例: `https://www.rehouse.co.jp/mansion/tokyo/` (東京都)
    - 例: `https://www.rehouse.co.jp/buy/mansion/prefecture/13/` (東京都詳細)

### 2. 詳細ページ
- **中古マンション:** `https://www.rehouse.co.jp/buy/mansion/bkdetail/[PROPERTY_ID]/`
    - 例: `https://www.rehouse.co.jp/buy/mansion/bkdetail/F07BAA01/`

## セレクタ (詳細ページ - 中古マンション)

### 基本情報
| 項目 | セレクタ | 備考 |
| :--- | :--- | :--- |
| **物件名** | `h1.headline1` | |
| **価格** | `.text-price-regular .amount` | 単位は `.text-price-regular .unit` |
| **物件画像** | `.sale-property-image-carousel .main-image` | `src`属性 |

### 物件概要テーブル
`tr.table-row` を走査し、ヘッダー (`.table-header` または `.label`) のテキストに基づいて値 (`.table-data` または `.content`) を取得する。

| 項目名 (thテキスト) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **物件種別** | `property_type` | 例: 中古マンション |
| **所在地** | `address` | `.span-item` や `a` タグ内のテキストを結合 |
| **交通** | `access` | 複数の駅情報が含まれる場合あり (`.break-line`) |
| **間取り** | `madori` | |
| **専有面積** | `exclusive_area` | |
| **築年月** | `built_date` | |
| **階数 / 階建** | `floor_info` | 例: 9階 / 地上14階建 |
| **向き** | `orientation` | |
| **管理費** | `management_fee` | (詳細テーブル内にある場合) |
| **修繕積立金** | `repair_reserve` | (詳細テーブル内にある場合) |
| **物件番号** | `property_id` | ページタイトルやURLから抽出可能 (例: F07BAA01) |

## 注意点
- 価格の表記は `span` タグで分かれている (`12,000` + `万円`)。
- テーブルの行 (`tr.table-row`) は `div` ではなく `table` 要素内にある場合と、レスポンシブ対応で `dl` 等に変わる可能性に注意（PC版は `table`）。
- 文字コードは `UTF-8`。
