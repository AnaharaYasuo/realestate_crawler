# サイト構造: 小田急不動産 (投資用)

## 概要
- **サイト名:** 小田急不動産 投資用
- **ベースURL:** `https://www.odakyu-chukai.com`
- **トップページ:** `https://www.odakyu-chukai.com/invest/`
- **一覧ページ:** `https://www.odakyu-chukai.com/invest/list/`

## URLパターン

### 1. 一覧ページ・カード
- **一覧URL:** `https://www.odakyu-chukai.com/invest/list/`
- **カードフォーカスURL:** `https://www.odakyu-chukai.com/invest/list/?focus=[ID]` (例: `B03131-000206`, `VI0023`)

### 2. 詳細ページ (フォールバック)
- **URLパターン:** `https://www.odakyu-chukai.com/(mansion|house|kodate|land|tochi|invest)/detail/[PROPERTY_ID]/`

## セレクタ・抽出仕様 (一覧カード `li.estate-block`)
`OdakyuInvestment` モデルに対応する全フィールドの抽出定義。

### 基本情報
| 項目名 | モデルフィールド | セレクタ / ソース | 備考 |
| :--- | :--- | :--- | :--- |
| **物件名** | `propertyName` | `.estate-block-name a` | |
| **価格** | `price`, `priceStr` | `.estate-price-item` | 万単位から数値変換 |
| **所在地** | `address`, `address1..3` | `.estate-info-list dl.address dt:contains('所在地') + dd` | |
| **交通** | `traffic1` | `.estate-info-list dl.address dt:contains('交通') + dd` | |

### 投資指標 (Investment Metrics)
| 項目名 | モデルフィールド | セレクタ / ソース | 備考 |
| :--- | :--- | :--- | :--- |
| **表面利回り** | `grossYield` | `.estate-info-catch` 正規表現 | `%` 表記をパーセント数値化 |
| **年間想定賃料** | `annualRent` | 表面利回り × 価格より逆算 | `int(price * grossYield / 100)` |
| **月額想定賃料** | `monthlyRent` | `annualRent // 12` | |

### 建物・土地・専有部スペック (`.estate-info-list dl dt/dd`)
| 項目名 (dt) | モデルフィールド | 処理ルール |
| :--- | :--- | :--- |
| **専有面積** | `tatemonoMensekiStr`, `tatemonoMenseki` | 区分所有等の専有面積を `tatemonoMenseki` に格納 |
| **建物面積** | `tatemonoMensekiStr`, `tatemonoMenseki` | 一棟/戸建ての建物面積を格納 |
| **土地面積** | `tochiMensekiStr`, `tochiMenseki` | 土地面積を格納 |
| **間取り** | `madori` (Model/Item属性) | |
| **階数** | `kaisuStr` | |
| **築年月** | `chikunengetsuStr`, `chikunengetsu` | 日付パース |
