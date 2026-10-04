# サイト構造: ミサワホーム不動産 (Misawa Home Real Estate)

## 概要
- **サイト名:** ミサワホーム不動産
- **ベースURL:** `https://www.misawa-mrd.co.jp`
- **タイプ:** 居住用（マンション, 戸建, 土地）、投資用

## URLパターン

### 1. 検索結果 (一覧ページ)
- **検索ベースURL:** `https://www.misawa-mrd.co.jp/search/`
- **種別パラメータ:** `type`
    - マンション: `type=1`
    - 戸建: `type=2`
    - 土地: `type=3`
    - 投資用: `type=4` (事業用)

### 2. 詳細ページ
- **URLパターン:** `https://www.misawa-mrd.co.jp/detail/[PROPERTY_ID]/`

## セレクタ (詳細ページ)

### 共通ヘッダー情報
### 抽出ルール
- **厳格な抽出**: 必須項目（物件名、価格、所在地、間取り、面積）が取得できない場合は、空欄をセットする代わりに例外を発生させ、エラーページとして保存する。
- **フォールバックの排除**: 以前使用されていた "-" などの安易なデフォルト値セットを廃止し、データの正確性を優先する。
| 項目 | セレクタ (ターゲット) | モデルフィールド |
| :--- | :--- | :--- |
| **物件名** | `h1.detail-title`, `h2`, `h1` | `propertyName` |
| **価格** | `.detail-price .num` | `price`, `priceStr` |
| **住所** | `.detail-address` | `address` |

### 物件概要テーブル
`table.detail-spec` 内の行 (`tr`) に `th` (項目名) と `td` (値) が含まれる。以下は、各モデルで管理される全フィールドと、対応するHTML上の項目名（推定含む）のマッピングである。

#### 共通フィールド (`MisawaCommon`)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **沿線・駅** | `railway1`, `station1`, `walkMinute1` | 徒歩分数はパースして数値化 |
| **土地権利** | `landTenure` | 所有権, 借地権など |
| **建ぺい率** | `kenpei` | % |
| **容積率** | `youseki` | % |
| **用途地域** | `zoning` | 第一種低層など |
| **引渡（入居予定日）** | `deliveryDate` | |
| **設備** | `facilities` | |
| **周辺環境** | `neighborhood` | |
| **学校区** | `schoolDistrict` | |
| **取引態様** | `transactionType` | 仲介, 売主など |
| **備考** | `remarks` | 制限事項など |

#### マンション (`MisawaMansion`)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **専有面積** | `senyuMenseki` | |
| **バルコニー面積** | `balconyMenseki` | |
| **所在階** | `floor` | |
| **構造** | `structure` | RC, SRCなど |
| **完成時期** | `completionDate` | 築年月 |
| **総戸数** | `totalUnits` | |
| **管理形態** | `managementType` | 全部委託など |
| **管理会社** | `managementCompany` | |
| **管理費** | `managementFee` | |
| **修繕積立金** | `repairReserve` | |
| **駐車場** | `parkingStatus` | |

#### 戸建 (`MisawaKodate`)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地面積** | `tochiMenseki` | |
| **建物面積** | `tatemonoMenseki` | |
| **間取り** | `madori` | |
| **構造** | `structure` | 木造など |
| **完成時期** | `completionDate` | |
| **建築確認番号** | `confirmationNumber` | |
| **接道状況** | `roadCondition` | |
| **私道負担** | `privateRoadFee` | |
| **セットバック** | `setback` | |
| **都市計画** | `urbanPlanning` | 市街化区域など |
| **駐車場** | `parkingCount` | |

#### 土地 (`MisawaTochi`)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地面積** | `tochiMenseki` | |
| **地目** | `landCategory` | 宅地など |
| **接道状況** | `roadCondition` | |
| **建築条件** | `buildingCondition` | あり/なし |
| **都市計画** | `urbanPlanning` | |
| **現況** | `currentStatus` | 更地, 古家ありなど |

#### 投資用・事業用 (`MisawaInvestment`)
| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地面積** | `tochiMenseki` | |
| **建物面積** | `tatemonoMenseki` | |
| **構造** | `structure` | |
| **完成時期/築年月** | `completionDate` | |
| **利回り** | `yield_rate` | 想定利回り |
| **年間予定賃料収入** | `annualIncome` | |
| **間取り** | `madori` | |
| **総戸数** | `totalUnits` | |
| **接道状況** | `roadCondition` | |
| **管理費等** | `managementFee` | 区分の場合 |
