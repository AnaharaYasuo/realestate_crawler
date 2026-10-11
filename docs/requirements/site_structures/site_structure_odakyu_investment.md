# サイト構造: 小田急不動産 (投資用)

## 概要
- **サイト名:** 小田急不動産 投資用 (LIFESCAPE1)
- **ベースURL:** `https://ls1.odakyu-chukai.com`
- **一覧ページ:** `https://ls1.odakyu-chukai.com/properties`

## 種別別 URL・並列化パラメータ (biz_kinds)
小田急投資物件サイトの検索フォームで定義されている `biz_kinds` パラメータに基づき、種別ごとの完全並列巡回を実施。

| 種別名 | パラメータ値 (`biz_kinds`) | スタートURL |
| :--- | :--- | :--- |
| **マンション（区分）** | `104` | `https://ls1.odakyu-chukai.com/properties?rest_record_filter[matching_attributes][0][key]=biz_kinds&rest_record_filter[matching_attributes][0][pattern]=in&rest_record_filter[matching_attributes][0][value][]=104` |
| **マンション（一棟）** | `103` | `https://ls1.odakyu-chukai.com/properties?rest_record_filter[matching_attributes][0][key]=biz_kinds&rest_record_filter[matching_attributes][0][pattern]=in&rest_record_filter[matching_attributes][0][value][]=103` |
| **アパート（一棟）** | `105` | `https://ls1.odakyu-chukai.com/properties?rest_record_filter[matching_attributes][0][key]=biz_kinds&rest_record_filter[matching_attributes][0][pattern]=in&rest_record_filter[matching_attributes][0][value][]=105` |
| **その他（ビル・土地・店舗等）** | `101,102,106,107,108` | `https://ls1.odakyu-chukai.com/properties?rest_record_filter[matching_attributes][0][key]=biz_kinds&rest_record_filter[matching_attributes][0][pattern]=in&rest_record_filter[matching_attributes][0][value][]=101,102,106,107,108` |

## URLパターン

### 1. 一覧ページ
- **一覧URL:** `https://ls1.odakyu-chukai.com/properties`
- **次ページURL:** `https://ls1.odakyu-chukai.com/properties?page=[PAGE_NUM]`

### 2. 詳細ページ
- **URLパターン:** `https://ls1.odakyu-chukai.com/properties/[PROPERTY_ID]` (例: `https://ls1.odakyu-chukai.com/properties/177378`)

## セレクタ・抽出仕様 (詳細ページ `物件概要` DL)
`OdakyuInvestment` モデルに対応する全フィールドの抽出定義。

### 基本情報
| 項目名 | モデルフィールド | セレクタ / ソース (dt / dd) | 備考 |
| :--- | :--- | :--- | :--- |
| **物件名** | `propertyName` | `h1` | ページメイン見出し |
| **価格** | `price`, `priceStr` | `dt:contains('価格') + dd` | 万単位から数値変換 (例: 15,000万円 -> 150000000) |
| **所在地** | `address`, `address1..3` | `dt:contains('所在地') + dd` | 都道府県・市区町村分割 |
| **交通** | `traffic1..3` | `dt:contains('交通') + dd` | 路線・駅・徒歩分数パース |

### 投資指標 (Investment Metrics)
| 項目名 | モデルフィールド | セレクタ / ソース | 備考 |
| :--- | :--- | :--- | :--- |
| **表面利回り** | `grossYield` | `dt:contains('想定利回り') + dd` | `%` 表記を数値化 (例: 5.16% -> Decimal('5.16')) |
| **年間想定賃料** | `annualRent` | 表面利回り × 価格より逆算 | `int(price * grossYield / 100)` |
| **月額想定賃料** | `monthlyRent` | `annualRent // 12` | |
| **現況** | `currentStatus` | `dt:contains('現況') + dd` | 賃貸中・空室等 |
| **オーナーチェンジ** | `ownerChange` (または備考/現況) | `dt:contains('オーナーチェンジ') + dd` | あり / なし |

### 建物・土地スペック (`dt:contains(...) + dd`)
| 項目名 (dt) | モデルフィールド | 処理ルール |
| :--- | :--- | :--- |
| **建物(専有)面積** | `tatemonoMensekiStr`, `tatemonoMenseki` | ㎡数値を抽出 |
| **土地面積** | `tochiMensekiStr`, `tochiMenseki` | ㎡数値を抽出 |
| **間取り** | `madori` | 1R, 1K等 |
| **総戸数** | `totalUnits` (または備考) | 戸数数値 |
| **建物構造** | `tatemonoKozo` | 木造, RC, 鉄骨造等 |
| **築年月** | `chikunengetsuStr`, `chikunengetsu` | 日付パース |
| **用途地域** | `youtoChiiki` | 第一種低層住居専用等 |
| **建ぺい率 / 容積率** | `kenpeiRitsu`, `yousekiRitsu` | %パース |
| **物件番号** | `propertyId` | 英数字コード (例: VD0121) |
