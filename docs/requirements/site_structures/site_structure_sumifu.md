# サイト構造: 住友不動産販売 (StepOn)

## 概要
- **サイト名:** 住友不動産販売 (StepOn)
- **ベースURL:** `https://www.stepon.co.jp`
- **タイプ:** 居住用（マンション, 戸建, 土地）

## URLパターン

### 1. 検索結果 (一覧ページ)
- **中古マンション:** `https://www.stepon.co.jp/mansion/[AREA_CODE]/`
    - 例: `https://www.stepon.co.jp/mansion/tokyo/` (要確認)
- **フリーワード検索:** `https://www.stepon.co.jp/search/list/...`

### 2. 詳細ページ
- **URLパターン:** `https://www.stepon.co.jp/mansion/detail_[PROPERTY_ID]/`
    - 例: `https://www.stepon.co.jp/mansion/detail_150B3030/`
    - IDは英数字8桁程度の形式 (例: `150B3030`)

## セレクタ (詳細ページ)

### 基本ヘッダー情報
| 項目 | セレクタ | 備考 |
| :--- | :--- | :--- |
| **物件名** | `h1` または `.heading-2` (要確認) | |
| **価格** | `.table-price-cell__item` (1つ目) | 価格テキストを含む |

### 抽出ルール
- **厳格な抽出**: 必須項目（物件名、価格、所在地、間取り、面積）が取得できない場合は、空欄をセットする代わりに例外を発生させ、エラーページとして保存する。
- **フォールバックの排除**: 以前使用されていた "-" などの安易なデフォルト値セットを廃止し、データの正確性を優先する。

### 物件概要テーブル (`table.table-detail`)
`table.table-detail` 内の `th` テキストに基づいて `td` を取得する。

| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **物件名** | `name` | th="物件名" (推定) |
| **物件番号** | `property_id` | th="物件番号" |
| **所在地** | `address` | th="所在地" |
| **価格** | `price` | th="価格" |
| **交通** | `access` | th="交通" |
| **間取り** | `madori` | th="間取り" |
| **専有面積** | `exclusive_area` | th="専有面積" (壁芯などの注記あり) |
| **構造・階建** | `structure` | th="構造" または "所在階/階建" |
| **築年月** | `built_date` | th="築年月" |
| **バルコニー面積** | `balcony_area` | th="バルコニー面積" |
| **向き** | `orientation` | th="向き" |
| **総戸数** | `total_units` | th="総戸数" |
| **管理費** | `management_fee` | th="管理費" |
| **修繕積立金** | `repair_reserve` | th="修繕積立金" |
| **管理方式** | `management_type` | th="管理方式", "管理形態" |
| **現況** | `current_status` | th="現況" |
| **引渡** | `delivery` | th="引渡" |
| **取引態様** | `transaction_type` | th="取引態様" |

## 注意点
- 文字コードは **Shift_JIS** (CP932) の可能性が高い。Python等でスクレイピングする際はデコード（`encoding='cp932'`）が必要。
- テーブル構造はシンプル (`tr > th, td`)。
