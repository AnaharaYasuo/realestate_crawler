# フィールド名統一規約

## 概要

このドキュメントは、全サイト共通で使用するモデルフィールド名の統一規約を定義します。
サイトが異なっていても、**同じ情報を保持する項目は必ず同一のフィールド名を使用する**ことで、データの一貫性とメンテナンス性を確保します。

## 基本原則

1. **統一性**: 同じ意味を持つ項目は、全サイト・全物件種別で同一のフィールド名を使用する
2. **日本語ベース**: フィールド名は日本語のローマ字表記を基本とする（例: `chikunengetsu`, `tochiMenseki`）
3. **一貫性**: 既存のフィールド名との整合性を保つ
4. **明確性**: フィールド名から内容が推測できるようにする

## 統一フィールド名一覧

### 基本情報

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 物件名 | `propertyName` | Text | 全物件種別共通 |
| 価格（文字列） | `priceStr` | Text | 元の表記を保持 |
| 価格（数値） | `price` | Integer | パース後の数値 |
| 所在地 | `address` | Text | 全物件種別共通 |
| 交通 | `traffic` | Text | 全物件種別共通 |

### 日付・時期

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 築年月（文字列） | `chikunengetsuStr` | Text | 元の表記（例: "2020年3月"） |
| 築年月（日付） | `chikunengetsu` | Date | パース後の日付型 |
| 築年月（投資用） | `yearBuilt` | Text | 一部サイトの投資用物件で使用（非推奨。`chikunengetsu`への統一を検討中） |
| 引渡時期 | `hikiwatashi` | Text | - |

### 面積関連

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 専有面積（文字列） | `senyuMensekiStr` | Text | マンション |
| 専有面積（数値） | `senyuMenseki` | Decimal | マンション |
| 土地面積（文字列） | `tochiMensekiStr` | Text | 戸建・土地・投資 |
| 土地面積（数値） | `tochiMenseki` | Decimal | 戸建・土地・投資 |
| 建物面積（文字列） | `tatemonoMensekiStr` | Text | 戸建・投資 |
| 建物面積（数値） | `tatemonoMenseki` | Decimal | 戸建・投資 |
| バルコニー面積（文字列） | `balconyMensekiStr` | Text | マンション |
| バルコニー面積（数値） | `balconyMenseki` | Decimal | マンション |

### 建物情報

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 間取り | `madori` | Text | 全物件種別 |
| 所在階 | `kaisu` | Text/Integer | マンション・投資 |
| 構造 | `kouzou` | Text | 全物件種別 |
| 階数構造 | `kaisuKouzou` | Text | 投資用物件 |
| 総階数 | `stories` | Integer | 全物件種別 |
| 総戸数 | `soukosu` | Integer | マンション・投資アパート |

### 費用関連

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 管理費（文字列） | `kanrihiStr` | Text | マンション |
| 管理費（数値） | `kanrihi` | Integer | マンション |
| 修繕積立金（文字列） | `syuzenTsumitateStr` | Text | マンション |
| 修繕積立金（数値） | `syuzenTsumitate` | Integer | マンション |

### 投資用物件専用

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 表面利回り | `grossYield` | Decimal | 投資用物件 |
| 年間想定賃料 | `annualRent` | Integer | 投資用物件 |
| 月間想定賃料 | `monthlyRent` | Integer | 投資用物件 |
| 現況 | `currentStatus` | Text | 投資用物件 |

### 土地・権利関連

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 用途地域 | `youtoChiiki` | Text | 戸建・土地・投資 |
| 土地権利 | `tochikenri` | Text | 全物件種別 |
| 接道状況 | `setsudou` | Text | 戸建・土地・投資 |
| 地目 | `chimoku` | Text | 土地・投資 |
| 建ぺい率（文字列）| `kenpeiStr` | Text | 投資用物件などで使用 |
| 建ぺい率（数値） | `kenpei` | Integer | 戸建・土地・投資 |
| 容積率（文字列） | `yousekiStr` | Text | 投資用物件などで使用 |
| 容積率（数値） | `youseki` | Integer | 戸建・土地・投資 |
| 現況 | `genkyo` | Text | 土地・投資 |
| 地勢 | `chisei` | Text | 土地 |
| 接道方位 | `douroMuki` | Text | 土地・戸建 |
| 接道種類 | `douroKubun` | Text | 土地・戸建 |
| 接道幅員 | `douroHaba` | Text | 土地・戸建 |
| 接道面 | `setsumen` | Decimal | 土地・戸建 |

### 管理・会社情報

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 向き | `saikou` | Text | マンション |
| 管理会社 | `kanriKaisya` | Text | マンション |
| 管理形態 | `kanriKeitai` | Text | マンション |
| 分譲会社 | `bunjoKaisya` | Text | マンション |
| 施工会社 | `sekouKaisya` | Text | マンション |
| 駐車場 | `tyusyajo` | Text | マンション・戸建 |

### 交通情報

| 項目名（日本語） | 統一フィールド名 | 型 | 備考 |
|----------------|----------------|-----|------|
| 路線数 | `railwayCount` | Integer | 全物件種別 |
| 路線1～5 | `railway1`～`railway5` | Text | 路線名 |
| 駅1～5 | `station1`～`station5` | Text | 駅名 |
| 徒歩分数1～5 | `railwayWalkMinute1`～`railwayWalkMinute5` | Integer | 駅からの徒歩分数 |
| バス利用1～5 | `busUse1`～`busUse5` | Integer | 0/1フラグ |
| バス停1～5 | `busStation1`～`busStation5` | Text | バス停名 |
| バス乗車時間1～5 | `busWalkMinute1`～`busWalkMinute5` | Integer | バス乗車時間 |

## 実装時の注意事項

### 1. パーサー実装時

```python
# ✅ 正しい例（統一フィールド名を使用）
item.chikunengetsuStr = specs.get("築年月", "")
item.tochiMenseki = converter.parse_menseki(specs.get("土地面積", ""))
item.kouzou = specs.get("構造", "")

# ❌ 誤った例（サイト固有の名前を使用）
item.yearBuilt = specs.get("築年月", "")  # NG
item.landArea = converter.parse_menseki(specs.get("土地面積", ""))  # NG
item.structure = specs.get("構造", "")  # NG
```

### 2. 日付フィールドの処理

築年月など日付型フィールドは、必ず以下の2つをセットで実装すること：

```python
# 1. 文字列フィールド（元の表記を保持）
item.chikunengetsuStr = specs.get("築年月", "")

# 2. 日付フィールド（パース後の日付型）
if item.chikunengetsuStr:
    item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
else:
    item.chikunengetsu = None
```

### 3. 面積フィールドの処理

面積フィールドも同様に、文字列と数値の両方を保持すること：

```python
# 文字列フィールド
item.tochiMensekiStr = specs.get("土地面積", "")

# 数値フィールド
if item.tochiMensekiStr:
    item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
else:
    item.tochiMenseki = Decimal(0)
```

## モデル定義との対応

各モデル（`SumifuMansion`, `MitsuiKodate`, `TokyuInvestmentKodate` など）は、
このドキュメントで定義されたフィールド名を使用して定義されています。

新規フィールドを追加する場合は：

1. このドキュメントに追加
2. 全サイトで同一のフィールド名を使用
3. `docs/database_schema.md` を更新
4. `README.md` のドキュメント一覧を更新

## 変更履歴

| 日付 | 変更内容 | 担当者 |
|------|---------|--------|
| 2026-02-14 | 初版作成。全5サイトの投資用物件パーサーでフィールド名を統一 | - |
