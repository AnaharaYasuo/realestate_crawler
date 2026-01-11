# データベース定義書 (Database Schema)

本プロジェクトで収集・保存されるデータベースの詳細なテーブル定義およびカラム一覧です。

## 1. データモデルの法則性

### テーブル命名規則
データベース内のテーブル名は、Django の `db_table` 設定に基づき以下の規則で命名されます。
- **形式**: `crawler_{company}{propertytype}`
- **例**: `crawler_mitsumansion`, `crawler_sumifuinvestment`, `crawler_tokyukodate`

### データ保持パターン (Dual Storage)
数値データについては、解析精度と集計の利便性を両立するため、以下の二重保持パターンを採用しています。
- **文字列フィールド (`...Str`)**: サイト上の表記をそのまま保持（例: `priceStr = "5,480万円"`）。
- **数値フィールド (`...`)**: 解析・正規化した数値を保持（例: `price = 54800000`）。
- **対象項目**: 価格 (`price`), 面積 (`senyuMenseki`), 各種費用 (`kanrihi`, `syuzenTsumitate`), 徒歩分数 (`railwayWalkMinute`) 等。

### モデル継承構造
重複コードを排除するため、以下の抽象基底クラスを用いてフィールド定義を共通化しています。
- **`SumifuModel`**: 住友不動産の Mansion, Kodate, Tochi で 69 フィールドを共有。
- **`MisawaCommon`**: ミサワホーム不動産の全種別で 21 フィールドを共有。

---

## 2. 共通基本情報 (Common Basic Info)

### 全モデル共通 8 フィールド (Universal Fields)
全ての物件種別・会社で必ず保持される基本項目です。

| 論理名 | 物理名 | 型 | 説明 |
| :--- | :--- | :--- | :--- |
| ID | `id` | Auto | 主キー |
| 物件名 | `propertyName` | Text | サイト上の物件タイトル |
| URL | `pageUrl` | Char(500) | **Index付与**。重複検知に使用 |
| 登録日 | `inputDate` | Date | クローリング実行日 |
| 登録日時 | `inputDateTime` | DateTime | 実行日時 |
| 価格(文字列) | `priceStr` | Text | 元の表記 (例: "5,480万円") |
| 価格(数値) | `price` | Integer | 円単位に正規化 |
| 住所 | `address` | Text | フル住所 |

---

## 3. 交通アクセス情報の構造 (Transportation Pattern)

各物件は最大 **5路線** までのアクセス情報を保持します。各路線ごとに以下の **8フィールド** が定義されており、合計 40 フィールドで構成されます（ミサワホーム不動産を除く）。

### 1路線あたりの 8 フィールド構成 (N=1~5)
1. `transfer{N}`: 乗り換え・案内情報
2. `railway{N}`: 沿線名
3. `station{N}`: 駅名
4. `railwayWalkMinute{N}Str`: 徒歩分数（元の表記）
5. `railwayWalkMinute{N}`: 徒歩分数（数値）
6. `busStation{N}`: バス停名
7. `busWalkMinute{N}Str`: バス停からの徒歩（元の表記）
8. `busWalkMinute{N}`: バス停からの徒歩（数値）

> [!NOTE]
> **ミサワホーム不動産の例外**: 交通情報は `railway1`, `station1`, `walkMinute1` の 3 フィールドのみの簡略化された構成となっています。

---

## 4. 物件種別ごとの詳細スペック (Specs by Type)

### マンション (Mansion)
| 論理名 | 物理名 | M | S | T | N | Mi | 説明 |
| :--- | :--- | :-: | :-: | :-: | :-: | :-: | :--- |
| 専有面積 | `senyuMenseki` | ○ | ○ | ○ | ○ | ○ | m2 |
| 間取り | `madori` | ○ | ○ | ○ | ○ | ○ | 3LDK 等 |
| 築年月 | `chikunengetsu`| ○ | ○ | ○ | ○ | ○ | |
| 所在階 | `floorType_kai`| ○ | ○ | ○ | ○ | ○ | 所在階 (数値) |
| 建物の階建 | `kaisu` | ○ | ○ | ○ | ○ | ○ | 地上〇階建 |
| 構造 | `kouzou` | ○ | ○ | ○ | ○ | ○ | RC, SRC 等 |

### 戸建て (Kodate) / 土地 (Tochi)
| 論理名 | 物理名 | M | S | T | N | Mi | 説明 |
| :--- | :--- | :-: | :-: | :-: | :-: | :-: | :--- |
| 土地面積 | `tochiMenseki` | ○ | ○ | ○ | ○ | ○ | |
| 建物面積 | `tatemonoMenseki`| ○ | ○ | ○ | ○ | ○ | 戸建てのみ |
| 接道状況 | `setsudou` | ○ | ○ | ○ | ○ | ○ | 道路幅員等 |
| 土地権利 | `tochikenri` | ○ | ○ | ○ | ○ | ○ | 所有権 等 |

### 投資用物件 (Investment)
| 論理名 | 物理名 | M | S | T | N | Mi | 説明 |
| :--- | :--- | :-: | :-: | :-: | :-: | :-: | :--- |
| 表面利回り | `grossYield` | ○ | ○ | ○ | ○ | ○ | % (数値) |
| 年間予定収入 | `annualIncome` | - | ○ | ○ | - | ○ | |
| 現在の状況 | `currentStatus` | ○ | ○ | ○ | ○ | - | 満室, 賃貸中 等 |
| 建物/専有面積 | `buildingArea` | ○ | ○ | ○ | ○ | ○ | |

---

## 5. 特記事項
- **マッピングエラー**: 解析に失敗した重要項目がある場合、`ReadPropertyNameException` がログ出力されます。
- **インデックス戦略**: 重複検知のため `pageUrl` に追加のインデックスが設定されています。
