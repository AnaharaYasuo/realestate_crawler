# サイト構造: 三井のリハウス (投資用)

## 概要
- **サイト名:** 三井のリハウス (投資用物件)
- **ベースURL:** `https://www.rehouse.co.jp`
- **タイプ:** 投資用 (一棟マンション, 一棟アパート, 区分マンションなど)

## URLパターン

### 1. 検索結果 (一覧ページ)
- **投資用物件検索:** `https://www.rehouse.co.jp/buy/investment/` (推定)
    - エリアや条件指定によりURLが変動
    - 例: `https://www.rehouse.co.jp/buy/investment/area/tokyo/`

### 2. 詳細ページ
- **URLパターン:** `https://www.rehouse.co.jp/buy/mansion/bkdetail/[PROPERTY_ID]/` (居抜きなど、区分は一般と同じURLの場合あり)
- **投資専用:** `https://www.rehouse.co.jp/buy/investment/bkdetail/[PROPERTY_ID]/` (要確認)

## セレクタ (詳細ページ)

### 共通ヘッダー・基本情報
| 項目 | セレクタ | モデルフィールド | 備考 |
| :--- | :--- | :--- | :--- |
| **物件名** | `title` (meta tag) or `h1` | `propertyName` | `title_selector` in loader |
| **価格** | `tr:contains("価格") td` | `price`, `priceStr` | |
| **住所** | `tr:contains("所在地") td` | `address` | |
| **交通** | `tr:has(td:contains("交通")) td` | `traffic` | |

### 物件概要テーブル
`tr.table-row` を走査し、ヘッダー (`td.table-header.label`) のテキストに基づいて値 (`td.table-data.content` または `td` 2番目) を取得する。

#### 投資指標 (Investment Metrics)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **表面利回り** (or 利回り) | `grossYield` | `%` を除去してパース |
| **想定年収** (or 年間想定賃料) | `annualRent` | |
| **現況** (or 賃貸状況) | `currentStatus` | |

### 抽出ルール
- **厳格な抽出**: 必須項目（物件名、価格、所在地、間取り、面積）が取得できない場合は、空欄をセットする代わりに例外を発生させ、エラーページとして保存する。
- **フォールバックの排除**: 以前使用されていた "-" などの安易なデフォルト値セットを廃止し、データの正確性を優先する。

#### 建物・土地詳細
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地面積** | `landArea` | `tochiMenseki` |
| **建物面積** | `buildingArea` | `tatemonoMenseki` |
| **専有面積** | `buildingArea` | 区分の場合 |
| **構造** | `structure` | |
| **築年月** | `yearBuilt` | |
| **総戸数** | `totalUnits` | アパート/一棟の場合 |
| **管理費** | `managementFee` | 区分の場合 |
| **修繕積立金** | `repairReserve` | 区分の場合 |

### 補足
- 詳細ページの構造は居住用とほぼ同じテーブルレイアウト (`tr.table-row`) を共有していることが多い。
- 「利回り」や「想定年収」の項目が追加されている点が主な違い。
