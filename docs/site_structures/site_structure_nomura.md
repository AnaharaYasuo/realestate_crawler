# サイト構造: ノムコム (野村不動産 - 居住用)

## 概要
- **サイト名:** ノムコム (nomu.com)
- **ベースURL:** `https://www.nomu.com`
- **タイプ:** 居住用（中古マンション, 新築一戸建て, 中古一戸建て, 土地）

## URLパターン

### 1. 検索結果 (一覧ページ)
- **中古マンション (エリア別):** `https://www.nomu.com/mansion/[AREA]/`
    - 例: `https://www.nomu.com/mansion/tokyo/`
- **一戸建て:** `https://www.nomu.com/house/`
- **土地:** `https://www.nomu.com/land/`

### 2. 詳細ページ
- **中古マンション:** `https://www.nomu.com/mansion/id/[PROPERTY_ID]/`
    - 例: `https://www.nomu.com/mansion/id/R5170373/`
- **一戸建て:** `https://www.nomu.com/house/id/[PROPERTY_ID]/`
- **土地:** `https://www.nomu.com/land/id/[PROPERTY_ID]/`

## セレクタ (詳細ページ - 中古マンション)

### 基本情報
| 項目 | セレクタ | 備考 |
| :--- | :--- | :--- |
| **物件名** | `h1` または `.detail_header_title` (要確認) | |
| **価格** | `.item_price .num` + `.item_price .unit` | 例: 4,999 万円 |
| **物件番号** | `.item_number` または テーブル内 `th:contains("物件番号") + td` | |

### 物件概要テーブル (`.item_table`)
`table.item_table` 内の `th` テキストに基づいて `td` を取得する。

| 項目名 (th) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **価格** | `price` | |
| **物件番号** | `property_id` | |
| **所在地** | `address` | リンクや地図リンクが含まれる場合あり |
| **交通** | `access` | 沿線・駅・徒歩分数 |
| **間取り** | `madori` | 例: 3LDK |
| **専有面積** | `exclusive_area` | 壁芯・内法などの注記あり |
| **バルコニー面積** | `balcony_area` | |
| **向き** | `orientation` | 南など |
| **その他面積** | `other_area` | 専用庭、テラスなど |
| **構造** | `structure` | RC造8階建て など |
| **所在階** | `floor` | |
| **築年月** | `built_date` | Date型へ変換推奨 |
| **総戸数** | `total_units` | |
| **土地権利** | `land_rights` | 所有権, 借地権など |
| **用途地域** | `zoning` | |
| **管理会社** | `management_company` | |
| **管理形態** | `management_type` | 全部委託, 自主管理など |
| **管理員** | `manager_type` | 日勤, 常駐など |
| **管理費** | `management_fee` | 月額 |
| **修繕積立金** | `repair_reserve` | 月額 |
| **その他使用料** | `other_fees` | 町内会費, インターネット使用料など |
| **駐車場** | `parking` | 空き状況など |
| **現況** | `current_status` | 空家, 居住中など |
| **引　渡** | `delivery` | 相談, 即時など |
| **取引態様** | `transaction_type` | 仲介, 売主など |
| **国土法届出** | `national_land_law` | 不要など |
| **備　考** | `remarks` | 施工会社, リノベーション情報など |
| **更新日** | `update_date` | |
| **次回更新予定日** | `next_update_date` | |

## 注意点
- 文字コードはUTF-8またはShift_JIS (レスポンスヘッダ確認)。
- テーブルの `th` には `scope="row"` 属性が付与されている。
- 一部の値（価格など）は `span` タグで装飾されているため、テキスト抽出時に注意。
