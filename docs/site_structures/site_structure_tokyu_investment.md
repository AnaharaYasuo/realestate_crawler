# サイト構造: 東急リバブル (投資用)

## 概要
- **サイト名:** 東急リバブル 投資用
- **ベースURL:** `https://www.livable.co.jp`
- **トップページ:** `https://www.livable.co.jp/toushi/`

## URLパターン

### 1. 検索結果 (一覧ページ)
種別ごとにベースURLが異なるパス構造。

- **マンション (区分):** `/fudosan-toushi/tatemono-bukken-all/conditions-use=mansion-kubun/`
- **マンション (一棟):** `/fudosan-toushi/tatemono-bukken-all/conditions-use=mansion-itto/`
- **アパート:** `/fudosan-toushi/tatemono-bukken-all/conditions-use=apart/`
- **ビル (一棟):** `/fudosan-toushi/tatemono-bukken-all/conditions-use=building-itto/`
- **店舗・事務所:** `/fudosan-toushi/tatemono-bukken-all/conditions-use=store-office/`
- **工場・倉庫:** `/fudosan-toushi/tatemono-bukken-all/conditions-use=factory-warehouse/`
- **土地:** `/fudosan-toushi/tochi-bukken-all/`

### 2. 詳細ページ
- **URLパターン:** `https://www.livable.co.jp/biz/pro/listing/[PROPERTY_ID]/`

## セレクタ (詳細ページ)
`TokyuInvestment` モデルに対応する全フィールドの抽出定義。

### 共通ヘッダー・基本情報
| 項目名 | モデルフィールド | セレクタ (推定) |
| :--- | :--- | :--- |
| **物件名** | `propertyName` | `h1.property-name` |
| **価格** | `price`, `priceStr` | `.price-value` |
| **交通** | `traffic` | `.traffic-text` |
| **所在地** | `address` | `.address-text` |

### 投資指標 (Investment Metrics)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **表面利回り** | `grossYield` | % |
| **満室時想定年収** | `annualRent` | 万円/年 |
| **現況** | `currentStatus` | 賃貸中, 空室など |

### 物件概要テーブル
`table.detail-spec` 等のテーブル構造から抽出。

#### 建物・専有部
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **専有面積** | `buildingArea` | 区分の場合 |
| **建物面積** | `buildingArea` | 一棟の場合 |
| **バルコニー面積** | `balconyArea` | 区分の場合 |
| **間取り** | `floorPlan` | |
| **築年月** | `yearBuilt` | |
| **構造** | `structure` | |
| **所在階** | `floor` | 区分の場合 |
| **階建** | `totalFloors` | 一棟の場合 |
| **総戸数** | `totalUnits` | |
| **管理費** | `managementFee` | |
| **修繕積立金** | `repairReserve` | |

#### 土地・法令
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地権利** | `landRights` | 所有権, 借地権など |
| **土地面積** | `landArea` | |
| **用途地域** | `zoning` | |
| **建ぺい率** | `kenpei` | % |
| **容積率** | `youseki` | % |
| **接道状況** | `startRoad` | |

> [!NOTE]
> 東急リバブルの投資サイトは、一般サイトと異なるドメイン (`livable.co.jp/biz/`) に遷移する場合があるため、クローラの実装時にはリダイレクトやドメイン変更に注意が必要。
