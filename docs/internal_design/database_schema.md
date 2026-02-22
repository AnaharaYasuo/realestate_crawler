# データベース定義書 (Database Schema) - 完全版

本プロジェクトで収集・保存されるデータベースの完全なテーブル定義およびカラム一覧です。
**バージョン 3.0**: 投資用物件のモデル継承・厳格化対応版

## 目次
1. [データモデルの法則性](#1-データモデルの法則性)
2. [Sumifu (住友不動産)](#2-sumifu-住友不動産)
3. [Mitsui (三井のリハウス)](#3-mitsui-三井のリハウス)
4. [Tokyu (東急リバブル)](#4-tokyu-東急リバブル)
5. [Nomura (野村の仲介+)](#5-nomura-野村の仲介)
6. [Misawa (ミサワホーム不動産)](#6-misawa-ミサワホーム不動産)

---

## 1. データモデルの法則性

### テーブル命名規則
- **形式**: `{company}_{propertytype}`
- **例**: `mitsui_mansion`, `sumifu_investment_kodate`, `tokyu_kodate`

### 共通継承構造
全てのモデルは、各不動産会社ごとの基底クラス（`BaseModel`）を継承します。
これにより、基本情報（URL、価格、住所、交通など）の一貫性を保証します。

### 厳格化フィールド (Strict Fields)
以下のフィールドは `null=False` で定義されており、欠損時はレコードが保存されません:

**モデルレベルで必須 (null=False):**
- `propertyName`, `pageUrl`, `inputDate`, `inputDateTime`, `price`, `address`
- `railway1` (または `traffic` - 生テキストの場合)

**物件種別ごと:**
- **Mansion**: `senyuMenseki` (専有面積), `madori` (間取り)
- **Kodate**: `tochiMenseki` (土地面積), `tatemonoMenseki` (建物面積)
- **Tochi**: `tochiMenseki` (土地面積), `kenpei` (建ぺい率), `youseki` (容積率)
- **Investment (Apartment/Kodate)**: `landArea` (土地面積), `buildingArea` (建物面積), `grossYield` (表面利回り)

### データ型凡例
- `Text`: TextField (無制限長)
- `Char(N)`: CharField (最大N文字)
- `Int`: IntegerField
- `Dec(M,D)`: DecimalField (最大M桁、小数点以下D桁)
- `Date`: DateField
- `DateTime`: DateTimeField
- `❌`: null=False (必須)
- `✅`: null=True (任意)

---

## 投資用物件の物件種別定義とフィールド仕様

> **重要**: 投資用モデル（InvestmentKodate/InvestmentApartment）を作成・修正する際は、必ずこのセクションを参照すること

### 物件種別の定義

#### Kodate（投資用一棟戸建て）
一戸建て住宅1棟を投資用として取得する物件

**対象物件例**:
- 一戸建て賃貸
- 店舗付住宅
- 事務所（一棟・小規模）

#### Apartment（投資用一棟アパート・マンション）
複数戸を含む一棟建物を投資用として取得する物件

**対象物件例**:
- 一棟アパート
- 一棟マンション
- 一棟ビル（テナント複数）

#### 区分マンション（対象外）
マンションの1室を区分所有する物件は、通常の投資用では扱わない

### 全サイト共通必須フィールド

| フィールド名 | 型 | Kodate | Apartment | 説明 |
|-------------|-----|--------|-----------|------|
| **grossYield** | Dec(5,2) | ✅ | ✅ | 表面利回り |
| **annualRent** | Integer | ✅ | ✅ | 年間賃料収入 |
| **monthlyRent** | Integer | ⚠️ | ✅ | 月額賃料（Kodateは物件による） |
| **currentStatus** | Text | ✅ | ✅ | 現況（賃貸中、空室等） |
| **tochiMenseki** | Dec(10,2) | ✅ | ✅ | 土地面積 |
| **tatemonoMenseki** | Dec(10,2) | ✅ | ✅ | 建物面積 |
| **kouzou** | Text | ✅ | ✅ | 構造（木造、RC等） |
| **chikunengetsuStr** | Text | ✅ | ✅ | 築年月 |
| **propertyType** | Text | ✅ | ✅ | 物件種別識別子 |

### 物件種別ごとの不要フィールド

#### Kodate（一棟戸建て）で不要なフィールド

| フィールド名 | 理由 |
|-------------|------|
| **kanrihi**（管理費） | 区分マンション専用。一棟物件は所有者が自己管理 |
| **syuzenTsumitate**（修繕積立金） | 区分マンション専用。一棟物件は所有者が自己管理 |
| **soukosu**（総戸数） | 戸建ては1戸のみ |
| **kaisu**（所在階） | 建物全体を所有するため不要 |
| **balconyArea**（バルコニー面積） | 戸建ては庭があり、バルコニー面積は意味がない |
| **senyuMenseki**（専有面積） | 区分マンション専用。戸建ては建物面積を使用 |
| **madori**（間取り） | 戸建ては単一間取りのため記載可だが任意 |

#### Apartment（一棟アパート・マンション）で不要なフィールド

| フィールド名 | 理由 |
|-------------|------|
| **kanrihi**（管理費） | 区分マンション専用。一棟物件は所有者が自己管理 |
| **syuzenTsumitate**（修繕積立金） | 区分マンション専用。一棟物件は所有者が自己管理 |
| **kaisu**（所在階） | 建物全体を所有するため不要 |
| **balconyArea**（バルコニー面積） | 一棟全体のため個別バルコニー面積は無意味 |
| **senyuMenseki**（専有面積） | 区分マンション専用。一棟は建物面積を使用 |
| **madori**（間取り） | 一棟物件は複数の間取りがあるため単一値では表現不可 |

### Apartmentの必須フィールド

- **soukosu**（総戸数）: 一棟アパート・マンションには必須

### モデル設計ルール

#### 新規モデル作成時
1. このセクションで物件種別の定義を確認
2. 必須フィールドリストを参照してモデルを設計
3. 不要フィールドリストに該当するフィールドは追加しない

#### 既存モデル修正時
1. このセクションで不要フィールドを確認
2. 該当フィールドを削除
3. マイグレーション作成・適用
4. パーサーからも該当フィールドの抽出処理を削除
5. **このdatabase_schema.mdのテーブル定義も必ず更新**

#### パーサー実装時
1. 実際のサイトの物件ページを確認
2. このセクションの「必須フィールド」が表示されているか検証
3. 表示されていないフィールドは抽出しない

### 絶対にやってはいけないこと

❌ **区分マンション専用フィールドを一棟物件に追加**
- `kanrihi`（管理費）
- `syuzenTsumitate`（修繕積立金）
- これらは区分所有者が管理組合に支払うもの
- 一棟所有者は自分で管理するため不要

❌ **フィールドが取得できない場合に安易にnull許容追加**
- まずサイト上に本当に情報がないか確認
- パーサーのセレクタが間違っている可能性を疑う
- 重要項目は厳格に（null=False）

❌ **物件種別を確認せずにフィールド追加**
- 他のモデル（Mansion等）からコピペしない
- 必ずこのセクションで物件種別に適したフィールドか確認

---

## 2. Sumifu (住友不動産)

### 2.1 SumifuModel (抽象基底クラス)

**継承モデル**: SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| 1 | propertyName | Text | ❌ | 物件名 |
| 2 | pageUrl | Char(500) | ❌ | URL (Index) |
| 3 | inputDate | Date | ❌ | 登録日 (auto_now_add) |
| 4 | inputDateTime | DateTime | ❌ | 登録日時 (auto_now_add) |
| 5 | priceStr | Text | ❌ | 価格(文字列) |
| 6 | price | Int | ❌ | 価格(数値) |
| 7 | address | Text | ❌ | 住所 |
| 8 | traffic | Text | ✅ | 交通 (生テキスト) |
| 9 | hikiwatashi | Text | ❌ | 引渡 |
| 10 | genkyo | Text | ❌ | 現況 |
| 11 | tochikenri | Text | ❌ | 土地権利 |
| 12 | torihiki | Text | ❌ | 取引態様 |
| 13 | biko | Text | ✅ | 備考 (blank=True) |
| 14 | address1 | Text | ✅ | 住所1 |
| 15 | address2 | Text | ✅ | 住所2 |
| 16 | address3 | Text | ✅ | 住所3 |
| 17 | addressKyoto | Text | ✅ | 京都住所 |
| 18 | railwayCount | Int | ✅ | 路線数 |
| 19 | busUse1 | Int | ✅ | バス利用フラグ |
| 20-59 | transfer1~5, railway1~5, station1~5, railwayWalkMinute1~5Str, railwayWalkMinute1~5, etc. | Text/Int | ✅ | 交通情報 (5路線分、TransportationMixinより) |

### 2.2 SumifuInvestmentKodate

**テーブル名**: `sumifu_investment_kodate`
**継承**: SumifuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (SumifuModel の全フィールド) | - | - | 基本情報・交通情報 |
| 60 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 61 | annualRent | Int | ❌ | 年間想定賃料 |
| 62 | monthlyRent | Int | ❌ | 月額賃料 |
| 63 | currentStatus | Text | ❌ | 現況 |
| 64 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 65 | tochiMenseki | Dec(10,2) | ❌ | 土地面積(数値) |
| 66 | tatemonoMensekiStr | Text | ❌ | 建物面積(文字列) |
| 67 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積(数値) |
| 68 | kouzou | Text | ❌ | 構造 |
| 69 | chikunengetsuStr| Text | ❌ | 築年月(文字列) |
| 70 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 71 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 72 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 73 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 74 | youseki | Int | ✅ | 容積率(数値) |
| 75 | setsudou | Text | ✅ | 接道 |
| 76 | chimoku | Text | ✅ | 地目 |
| 77 | youtoChiiki | Text | ✅ | 用途地域 (blank=True) |
| 78 | tochikenri | Text | ❌ | 土地権利 |
| 79 | propertyType | Text | ❌ | 物件種別 ("Kodate") |

### 2.3 SumifuInvestmentApartment

**テーブル名**: `sumifu_investment_apartment`
**継承**: SumifuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (SumifuModel の全フィールド) | - | - | 基本情報・交通情報 |
| 60 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 61 | annualRent | Int | ❌ | 年間想定賃料 |
| 62 | monthlyRent | Int | ❌ | 月額賃料 |
| 63 | currentStatus | Text | ❌ | 現況 |
| 64 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 65 | tochiMenseki | Dec(10,2) | ❌ | 土地面積(数値) |
| 66 | tatemonoMensekiStr| Text | ❌ | 建物面積(文字列) |
| 67 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積(数値) |
| 68 | kouzou | Text | ❌ | 構造 |
| 69 | chikunengetsuStr| Text | ❌ | 築年月(文字列) |
| 70 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 71 | soukosuStr | Text | ✅ | 総戸数(文字列) |
| 72 | soukosu | Int | ✅ | 総戸数(数値) |
| 73 | kaisu | Int | ✅ | 建物階数(数値) |
| 74 | kaisuStr | Text | ✅ | 建物階数(文字列) |
| 75 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 76 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 77 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 78 | youseki | Int | ✅ | 容積率(数値) |
| 79 | setsudou | Text | ✅ | 接道 (blank=True) |
| 80 | chimoku | Text | ✅ | 地目 (blank=True) |
| 81 | youtoChiiki | Text | ✅ | 用途地域 (blank=True) |
| 82 | tochikenri | Text | ❌ | 土地権利 |
| 83 | propertyType | Text | ❌ | 物件種別 ("Apartment") |

### 2.4 SumifuMansion

**テーブル名**: `sumifu_mansion`
**継承**: SumifuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (SumifuModel の全フィールド) | - | - | 基本情報 |
| 60 | madori | Text | ✅ | 間取り |
| 61 | senyuMensekiStr | Text | ✅ | 専有面積(文字列) |
| 62 | senyuMenseki | Dec(8,3) | ✅ | 専有面積(数値) |
| 63 | kaisu | Text | ✅ | 所在階 |
| 64 | chikunengetsuStr | Text | ✅ | 築年月(文字列) |
| 65 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 66 | balconyMensekiStr | Text | ✅ | バルコニー面積(文字列) |
| 67 | saikouKadobeya | Text | ✅ | 採光・角部屋等 |
| 68 | saikou | Text | ✅ | 採光方向 |
| 69 | kadobeya | Text | ✅ | 角部屋フラグ |
| 70 | soukosuStr | Text | ✅ | 総戸数(文字列) |
| 71 | soukosu | Int | ✅ | 総戸数(数値) |
| 72 | kanriKeitaiKaisya | Text | ✅ | 管理形態・会社 |
| 73 | kanriKeitai | Text | ✅ | 管理形態 |
| 74 | kanriKaisya | Text | ✅ | 管理会社 |
| 75 | kanrihiStr | Text | ✅ | 管理費(文字列) |
| 76 | kanrihi | Int | ✅ | 管理費(数値) |
| 77 | syuzenTsumitateStr | Text | ✅ | 修繕積立金(文字列) |
| 78 | syuzenTsumitate | Int | ✅ | 修繕積立金(数値) |
| 79 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 80 | kouzou | Text | ✅ | 構造 |
| 81 | sonotaHiyouStr | Text | ✅ | その他費用 (blank=True) |
| 82 | bunjoKaisya | Text | ✅ | 分譲会社 (blank=True) |
| 83 | sekouKaisya | Text | ✅ | 施工会社 (blank=True) |
| 84-87 | floorType_kai/chijo/chika/kouzou | Int/Text | ✅ | 階数詳細情報 |
| 88 | kyutaishin | Int | ✅ | 旧耐震フラグ |
| 89 | balconyMenseki | Dec(6,3) | ✅ | バルコニー面積(数値) |
| 90 | senyouNiwaMenseki | Dec(6,3) | ✅ | 専用庭面積 |
| 91 | roofBalconyMenseki | Dec(6,3) | ✅ | ルーフバルコニー面積 |
| 92 | kanrihi_p_heibei | Dec(7,3) | ✅ | ㎡単価管理費 |
| 93 | syuzenTsumitate_p_heibei | Dec(7,3) | ✅ | ㎡単価修繕積立金 |
| 94 | kaisuKouzou | Text | ✅ | 階数・構造（統合ラベル対応） |
| 95 | kaisuStr | Text | ✅ | 階数(文字列) |

### 2.5 SumifuKodate

**テーブル名**: `sumifu_kodate`
**継承**: SumifuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (SumifuModel の全フィールド) | - | - | 基本情報 |
| 60 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 61 | tochiMenseki | Dec(10,3) | ❌ | 土地面積(数値) |
| 62 | tatemonoMensekiStr | Text | ❌ | 建物面積(文字列) |
| 63 | tatemonoMenseki | Dec(10,3) | ❌ | 建物面積(数値) |
| 64 | madori | Text | ❌ | 間取り |
| 65 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 66 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 67-69 | kaisuKouzou, kaisu, kouzou | Text | ❌ | 階数・構造情報 |
| 70 | chimokuChisei | Text | ❌ | 地目・地勢 |
| 71 | chimoku | Text | ❌ | 地目 |
| 72 | chisei | Text | ❌ | 地勢 |
| 73 | setsudou | Text | ❌ | 接道状況 |
| 74-77 | douro, douroMuki, douroHaba, douroKubun | Text/Dec | ❌/✅ | 道路情報 |
| 78 | setsumen | Dec(6,3) | ✅ | 接面 |
| 79 | kenpeiYousekiStr | Text | ❌ | 建ぺい・容積率(文字列) |
| 80 | kenpei | Int | ✅ | 建ぺい率 |
| 81 | youseki | Int | ✅ | 容積率 |
| 82 | chiikiChiku | Text | ❌ | 地域地区 |
| 83 | kuiki | Text | ❌ | 都市計画区域 |
| 84 | youtoChiiki | Text | ❌ | 用途地域 |
| 85 | boukaChiiki | Text | ❌ | 防火地域 |
| 86 | saikenchiku | Text | ❌ | 再建築可否 |
| 87 | sonotaChiiki | Text | ❌ | その他地域 |
| 88 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 89 | kokudoHou | Text | ❌ | 国土法 |
| 90 | kaisuStr | Text | ✅ | 階数(文字列) |

### 2.6 SumifuTochi

**テーブル名**: `sumifu_tochi`
**継承**: SumifuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (SumifuModel の全フィールド) | - | - | 基本情報 |
| 60 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 61 | tochiMenseki | Dec(10,3) | ❌ | 土地面積(数値) |
| 62-64 | chimokuChisei, chimoku, chisei | Text | ❌ | 地目・地勢 |
| 65 | setsudou | Text | ❌ | 接道状況 |
| 66-69 | douro, douroMuki, douroHaba, douroKubun | Text/Dec | ❌/✅ | 道路情報 |
| 70 | setsumen | Dec(6,3) | ✅ | 接面 |
| 71 | kenpeiYousekiStr | Text | ❌ | 建ぺい・容積率(文字列) |
| 72 | kenpei | Int | ✅ | 建ぺい率 |
| 73 | youseki | Int | ✅ | 容積率 |
| 74-80 | chiikiChiku, kuiki, youtoChiiki, boukaChiiki, saikenchiku, sonotaChiiki, kenchikuJoken | Text | ❌ | 用途・建築条件等 |
| 81 | kokudoHou | Text | ❌ | 国土法 |

---

## 3. Mitsui (三井のリハウス)

### 3.1 MitsuiModel (抽象基底クラス)

**継承モデル**: MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| 1 | propertyName | Text | ❌ | 物件名 |
| 2 | pageUrl | Char(500) | ❌ | URL (Index) |
| 3 | inputDate | Date | ❌ | 登録日 |
| 4 | inputDateTime | DateTime | ❌ | 登録日時 |
| 5 | priceStr | Text | ❌ | 価格(文字列) |
| 6 | price | Int | ❌ | 価格(数値) |
| 7 | address | Text | ❌ | 住所 |
| 8-47 | transfer1~5, railway1~5, station1~5, etc. | Text/Int | ✅ | 交通情報 (5路線分、TransportationMixinより) |

### 3.2 MitsuiMansion

**テーブル名**: `mitsui_mansion`
**継承**: MitsuiModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MitsuiModel の全フィールド) | - | - | 基本情報 |
| 48 | madori | Text | ❌ | 間取り |
| 49 | senyuMensekiStr | Text | ❌ | 専有面積(文字列) |
| 50 | senyuMenseki | Dec(10,3) | ❌ | 専有面積(数値) |
| 51 | kaisu | Text | ❌ | 所在階 |
| 52 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 53 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 54 | balconyMensekiStr | Text | ❌ | バルコニー面積(文字列) |
| 55 | saikouKadobeya | Text | ❌ | 採光・角部屋等 |
| 56 | saikou | Text | ❌ | 採光方向 |
| 57 | kadobeya | Text | ❌ | 角部屋フラグ |
| 58 | soukosuStr | Text | ❌ | 総戸数(文字列) |
| 59 | soukosu | Int | ✅ | 総戸数(数値) |
| 60 | kanriKeitaiKaisya | Text | ❌ | 管理形態・会社 |
| 61 | kanriKeitai | Text | ❌ | 管理形態 |
| 62 | kanriKaisya | Text | ❌ | 管理会社 |
| 63 | kanrihiStr | Text | ❌ | 管理費(文字列) |
| 64 | kanrihi | Int | ✅ | 管理費(数値) |
| 65 | syuzenTsumitateStr | Text | ❌ | 修繕積立金(文字列) |
| 66 | syuzenTsumitate | Int | ✅ | 修繕積立金(数値) |
| 67 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 68 | kouzou | Text | ❌ | 構造 |
| 69 | sonotaHiyouStr | Text | ✅ | その他費用 (blank=True) |
| 70 | bunjoKaisya | Text | ✅ | 分譲会社 (blank=True) |
| 71 | sekouKaisya | Text | ✅ | 施工会社 (blank=True) |

### 3.3 MitsuiKodate

**テーブル名**: `mitsui_kodate`
**継承**: MitsuiModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MitsuiModel の全フィールド) | - | - | 基本情報 |
| 48 | tochiMensekiStr | Text | ✅ | 土地面積(文字列) |
| 49 | tochiMenseki | Dec(10,3) | ✅ | 土地面積(数値) |
| 50 | tatemonoMensekiStr | Text | ✅ | 建物面積(文字列) |
| 51 | tatemonoMenseki | Dec(10,3) | ✅ | 建物面積(数値) |
| 52 | kaisuKouzou | Text | ✅ | 階数・構造 |
| 53 | kaisu | Text | ✅ | 階数 |
| 54 | kouzou | Text | ✅ | 構造 |
| 55 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 56 | chimoku | Text | ✅ | 地目 |
| 57 | kenpei | Dec(10,3) | ✅ | 建ぺい率 |
| 58 | youseki | Dec(10,3) | ✅ | 容積率 |
| 59 | youtoChiiki | Text | ✅ | 用途地域 |
| 60 | kuiki | Text | ✅ | 都市計画区域 |
| 61 | setsudou | Text | ✅ | 接道 |
| 62 | douroMuki | Text | ✅ | 道路向き |
| 63 | douroHaba | Dec(10,3) | ✅ | 道路幅 |
| 64 | douroKubun | Text | ❌ | 道路区分 |
| 65 | setsumen | Dec(10,3) | ✅ | 接面 |
| 66 | sonotaHiyouStr | Text | ✅ | その他費用 (blank=True) |

### 3.4 MitsuiTochi

**テーブル名**: `mitsui_tochi`
**継承**: MitsuiModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MitsuiModel の全フィールド) | - | - | 基本情報 |
| 48 | tochiMenseki | Dec(10,2) | ❌ | 土地面積 |
| 49 | kenpei | Int | ✅ | 建ぺい率 |
| 50 | youseki | Int | ✅ | 容積率 |
| 51 | chimoku | Text | ✅ | 地目 |

### 3.5 MitsuiInvestmentKodate

**テーブル名**: `mitsui_investment_kodate`
**継承**: MitsuiModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MitsuiModel の全フィールド) | - | - | 基本情報 |
| 48 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 49 | annualRent | Int | ❌ | 年間想定賃料 |
| 50 | monthlyRent | Int | ❌ | 月額賃料 |
| 51 | currentStatus | Text | ❌ | 現況 |
| 52 | kouzou | Text | ❌ | 構造 |
| 53 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 54 | tochiMensekiStr | Text | ✅ | 土地面積(文字列) |
| 55 | tochiMenseki | Dec(10,2) | ❌ | 土地面積(数値) |
| 56 | tatemonoMensekiStr| Text | ✅ | 建物面積(文字列) |
| 57 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積(数値) |
| 58 | setsudou | Text | ✅ | 接道 |
| 59 | chimoku | Text | ✅ | 地目 |
| 60 | youtoChiiki | Text | ✅ | 用途地域 |
| 61 | kenpei | Dec(10,3) | ✅ | 建ぺい率 |
| 62 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 63 | youseki | Dec(10,3) | ✅ | 容積率 |
| 64 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 65 | kaisuStr | Text | ✅ | 階数(文字列) |
| 66 | propertyType | Text | ❌ | 物件種別 ("Kodate") |

### 3.6 MitsuiInvestmentApartment

**テーブル名**: `mitsui_investment_apartment`
**継承**: MitsuiModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MitsuiModel の全フィールド) | - | - | 基本情報 |
| 48 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 49 | annualRent | Int | ❌ | 年間想定賃料 |
| 50 | monthlyRent | Int | ❌ | 月額賃料 |
| 51 | currentStatus | Text | ❌ | 現況 |
| 52 | kouzou | Text | ❌ | 構造 |
| 53 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 54 | soukosu | Int | ✅ | 総戸数 |
| 55 | kanrihi | Int | ✅ | 管理費 |
| 56 | syuzenTsumitate | Int | ✅ | 修繕積立金 |
| 57 | tochiMensekiStr | Text | ✅| 土地面積(文字列) |
| 58 | tochiMenseki | Dec(10,2) | ✅ | 土地面積(数値) |
| 59 | tatemonoMensekiStr| Text | ✅ | 建物面積(文字列) |
| 60 | tatemonoMenseki | Dec(10,2) | ✅ | 建物面積(数値) |
| 61 | kenpei | Dec(10,3) | ✅ | 建ぺい率 |
| 62 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 63 | youseki | Dec(10,3) | ✅ | 容積率 |
| 64 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 65 | setsudou | Text | ✅ | 接道 |
| 66 | chimoku | Text | ✅ | 地目 |
| 67 | youtoChiiki | Text | ✅ | 用途地域 |
| 68 | tochikenri | Text | ✅ | 土地権利 |
| 69 | propertyType | Text | ❌ | 物件種別 ("Apartment") |

---

## 4. Tokyu (東急リバブル)

### 4.1 TokyuModel (抽象基底クラス)

**継承モデル**: TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestment, TokyuInvestmentApartment

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| 1 | propertyName | Text | ❌ | 物件名 |
| 2 | pageUrl | Char(500) | ❌ | URL |
| 3 | price | Int | ❌ | 価格 |
| 4 | address | Text | ❌ | 住所 |
| 5 | traffic | Text | ❌ | 交通 (生テキスト/構造化複合) |
| 6-45 | transfer1~5, railway1~5, station1~5, etc. | Text/Int | ✅ | 交通情報 (5路線分、TransportationMixinより) |

### 4.2 TokyuMansion

**テーブル名**: `tokyu_mansion`
**継承**: TokyuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (TokyuModel の全フィールド) | - | - | 基本情報 |
| 46 | madori | Text | ❌ | 間取り |
| 47 | senyuMensekiStr | Text | ❌ | 専有面積(文字列) |
| 48 | senyuMenseki | Dec(8,3) | ❌ | 専有面積(数値) |
| 49 | kaisu | Text | ❌ | 所在階 |
| 50 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 51 | chikunengetsu | Date | ✅ | 築年月(日付) |
| 52 | kanrihiStr | Text | ❌ | 管理費(文字列) |
| 53 | kanrihi | Int | ✅ | 管理費(数値) |
| 54 | syuzenTsumitateStr | Text | ❌ | 修繕積立金(文字列) |
| 55 | syuzenTsumitate | Int | ✅ | 修繕積立金(数値) |
| 56 | sonotaHiyouStr | Text | ✅ | その他費用 (blank=True) |
| 57 | balconyMensekiStr | Text | ❌ | バルコニー面積(文字列) |
| 58 | balconyMenseki | Dec(8,3) | ✅ | バルコニー面積(数値) |
| 59 | saikou | Text | ❌ | 向き |
| 60 | kaisuStr | Text | ❌ | 階数表示 |
| 61 | tatemonoKaisu | Text | ❌ | 建物階数 |
| 62 | kouzou | Text | ❌ | 構造 |
| 63 | soukosu | Text | ❌ | 総戸数 |
| 64 | bunjoKaisya | Text | ✅ | 分譲会社 (blank=True) |
| 65 | sekouKaisya | Text | ✅ | 施工会社 (blank=True) |
| 66 | kanriKaisya | Text | ✅ | 管理会社 (blank=True) |
| 67 | kanriKeitai | Text | ❌ | 管理形態 |
| 68 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 69 | cyusyajo | Text | ✅ | 駐輪場 (blank=True) |
| 70 | bikeokiba | Text | ✅ | バイク置場 (blank=True) |

### 4.3 TokyuKodate

**テーブル名**: `tokyu_kodate`
**継承**: TokyuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (TokyuModel の全フィールド) | - | - | 基本情報 |
| 46 | tochiMenseki | Dec(10,2) | ❌ | 土地面積 |
| 47 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積 |
| 48 | madori | Text | ❌ | 間取り |
| 49 | kouzou | Text | ✅ | 構造 |
| 50 | chikunengetsu | Date | ✅ | 築年月 |

### 4.4 TokyuTochi

**テーブル名**: `tokyu_tochi`
**継承**: TokyuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (TokyuModel の全フィールド) | - | - | 基本情報 |
| 46 | tochiMenseki | Dec(10,2) | ✅ | 土地面積 |
| 47 | kenpei | Int | ✅ | 建ぺい率 |
| 48 | youseki | Int | ✅ | 容積率 |
| 49 | chimoku | Text | ✅ | 地目 |

### 4.5 TokyuInvestmentKodate

**テーブル名**: `tokyu_investment_kodate`
**継承**: TokyuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (TokyuModel の全フィールド) | - | - | 基本情報 |
| 46 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 47 | annualRent | Int | ❌ | 年間想定賃料 |
| 48 | currentStatus | Text | ❌ | 現況 |
| 49 | propertyType | Text | ❌ | 物件種別 |
| 50 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 51 | tochiMenseki | Dec(10,2) | ❌ | 土地面積(数値) |
| 52 | tatemonoMensekiStr | Text | ❌ | 建物面積(文字列) |
| 53 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積(数値) |
| 54 | kouzou | Text | ❌ | 構造 |
| 55 | kaisu | Text | ❌ | 階数 |
| 56 | totalFloors | Text | ❌ | 建物階数 |
| 57 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 58 | soukosu | Int | ✅ | 総戸数 |
| 59 | floorPlan | Text | ❌ | 間取り |
| 60 | balconyArea | Dec(6,2) | ✅ | バルコニー面積 |
| 61 | kanrihi | Int | ✅ | 管理費 |
| 62 | syuzenTsumitate | Int | ✅ | 修繕積立金 |
| 63 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 64 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 65 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 66 | youseki | Int | ✅ | 容積率(数値) |
| 61 | kenpei | Int | ✅ | 建ぺい率 |
| 62 | youseki | Int | ✅ | 容積率 |
| 63 | youtoChiiki | Text | ❌ | 用途地域 |
| 64 | startRoad | Text | ❌ | 接道道路 |
| 65 | tochikenri | Text | ❌ | 土地権利 |

### 4.6 TokyuInvestmentApartment

**テーブル名**: `tokyu_investment_apartment`
**継承**: TokyuModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (TokyuModel の全フィールド) | - | - | 基本情報 |
| 46 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 47 | annualRent | Int | ❌ | 年間想定賃料 |
| 48 | monthlyRent | Int | ❌ | 月額賃料 |
| 49 | currentStatus | Text | ❌ | 現況 |
| 50 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 51 | tochiMenseki | Dec(10,2) | ❌ | 土地面積(数値) |
| 52 | tatemonoMensekiStr| Text | ❌ | 建物面積(文字列) |
| 53 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積(数値) |
| 54 | kouzou | Text | ❌ | 構造 |
| 55 | totalFloors | Text | ❌ | 建物階数 |
| 56 | chikunengetsuStr | Text | ❌ | 築年月(文字列) |
| 57 | soukosuStr | Text | ✅ | 総戸数(文字列) |
| 58 | soukosu | Int | ✅ | 総戸数(数値) |
| 61 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 62 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 63 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 64 | youseki | Int | ✅ | 容積率(数値) |
| 60 | youtoChiiki | Text | ❌ | 用途地域 |
| 61 | tochikenri | Text | ❌ | 土地権利 |
| 62 | setsudou | Text | ❌ | 接道 |
| 63 | chimoku | Text | ❌ | 地目 |
| 64 | propertyType | Text | ❌ | 物件種別 ("Apartment") |

---

## 5. Nomura (野村の仲介+)

### 5.1 NomuraModel (抽象基底クラス)

**継承モデル**: NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| 1 | propertyName | Text | ❌ | 物件名 |
| 2 | pageUrl | Char(500) | ❌ | URL |
| 3 | inputDate | Date | ❌ | 登録日 |
| 4 | inputDateTime | DateTime | ❌ | 登録日時 |
| 5 | priceStr | Text | ❌ | 価格(文字列) |
| 6 | price | Int | ❌ | 価格(数値) |
| 7 | address | Text | ❌ | 住所 |
| 8 | traffic | Text | ❌ | 交通 (生テキスト) |
| 9-48 | transfer1~5, railway1~5, station1~5, etc. | Text/Int | ✅ | 交通情報 (5路線分、TransportationMixinより) |

### 5.2 NomuraMansion

**テーブル名**: `nomura_mansion`
**継承**: NomuraModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (NomuraModel の全フィールド) | - | - | 基本情報 |
| 49 | madori | Text | ❌ | 間取り |
| 50 | senyuMensekiStr | Text | ❌ | 専有面積(文字列) |
| 51 | senyuMenseki | Dec(10,3) | ❌ | 専有面積(数値) |
| 52 | balconyMensekiStr | Text | ❌ | バルコニー面積(文字列) |
| 53 | balconyMenseki | Dec(10,3) | ✅ | バルコニー面積(数値) |
| 54 | saikou | Text | ❌ | 向き |
| 54 | otherArea | Text | ✅ | その他面積 (blank=True) |
| 55 | kouzou | Text | ❌ | 構造 |
| 56 | kaisu | Text | ❌ | 所在階 |
| 57 | chikunengetsuStr | Text | ❌ | 築年月 |
| 58 | soukosu | Text | ❌ | 総戸数 |
| 59 | tochikenri | Text | ❌ | 土地権利 |
| 60 | youtoChiiki | Text | ❌ | 用途地域 |
| 61 | kanriKaisya | Text | ❌ | 管理会社 |
| 62 | kanriKeitai | Text | ❌ | 管理形態 |
| 63 | manager | Text | ❌ | 管理員 |
| 64 | kanrihiStr | Text | ❌ | 管理費(文字列) |
| 65 | kanrihi | Int | ✅ | 管理費(数値) |
| 66 | syuzenTsumitateStr | Text | ❌ | 修繕積立金(文字列) |
| 67 | syuzenTsumitate | Int | ✅ | 修繕積立金(数値) |
| 68 | otherFees | Text | ✅ | その他費用 (blank=True) |
| 69 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 70 | Stories | Int | ✅ | 階数(数値) |

### 5.3 NomuraKodate

**テーブル名**: `nomura_kodate`
**継承**: NomuraModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (NomuraModel の全フィールド) | - | - | 基本情報 |
| 49 | tochiMensekiStr| Text | ❌ | 土地面積(文字列) |
| 50 | tochiMenseki | Dec(10,2) | ✅ | 土地面積(数値) |
| 51 | tatemonoMensekiStr| Text | ❌ | 建物面積(文字列) |
| 52 | tatemonoMenseki | Dec(10,2) | ✅ | 建物面積(数値) |
| 53 | kouzou | Text | ❌ | 構造 |
| 54 | chikunengetsuStr | Text | ❌ | 築年月 |
| 55 | tyusyajo | Text | ✅ | 駐車場 (blank=True) |
| 56 | tochikenri | Text | ❌ | 土地権利 |
| 57 | chimoku | Text | ❌ | 地目 |
| 58 | privateRoadBurden | Text | ✅ | 私道負担 (blank=True) |
| 59 | setback | Text | ✅ | セットバック (blank=True) |
| 60 | cityPlanning | Text | ❌ | 都市計画 |
| 61 | youtoChiiki | Text | ❌ | 用途地域 |
| 62 | kenpeiStr | Text | ❌ | 建ぺい率(文字列) |
| 63 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 64 | yousekiStr | Text | ❌ | 容積率(文字列) |
| 65 | youseki | Int | ✅ | 容積率(数値) |
| 66 | setsudou | Text | ❌ | 接道状況 |
| 67 | facilities | Text | ✅ | 設備 (blank=True) |

### 5.4 NomuraTochi

**テーブル名**: `nomura_tochi`
**継承**: NomuraModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (NomuraModel の全フィールド) | - | - | 基本情報 |
| 49 | tochiMensekiStr| Text | ❌ | 土地面積(文字列) |
| 50 | tochiMenseki | Dec(10,2) | ✅ | 土地面積(数値) |
| 51 | tochikenri | Text | ❌ | 土地権利 |
| 52 | chimoku | Text | ❌ | 地目 |
| 53 | kenpeiStr | Text | ❌ | 建ぺい率(文字列) |
| 54 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 55 | yousekiStr | Text | ❌ | 容積率(文字列) |
| 56 | youseki | Int | ✅ | 容積率(数値) |

### 5.5 NomuraInvestmentKodate

**テーブル名**: `nomura_investment_kodate`
**継承**: NomuraModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (NomuraModel の全フィールド) | - | - | 基本情報 |
| 49 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 50 | annualRent | Int | ❌ | 年間想定賃料 |
| 51 | tochiMenseki | Dec(10,2) | ❌ | 土地面積 |
| 52 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積 |
| 53 | kouzou | Text | ✅ | 構造 |
| 54 | chikunengetsuStr | Text | ❌ | 築年月 |
| 55 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 56 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 57 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 58 | youseki | Int | ✅ | 容積率(数値) |
| 59 | setsudou | Text | ✅ | 接道 |
| 60 | chimoku | Text | ✅ | 地目 |
| 61 | youtoChiiki | Text | ✅ | 用途地域 |
| 62 | tochikenri | Text | ✅ | 土地権利 |
| 63 | propertyType | Text | ❌ | 物件種別 ("Kodate") |

### 5.6 NomuraInvestmentApartment

**テーブル名**: `nomura_investment_apartment`
**継承**: NomuraModel

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (NomuraModel の全フィールド) | - | - | 基本情報 |
| 49 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 50 | annualRent | Int | ❌ | 年間想定賃料 |
| 51 | monthlyRent | Int | ❌ | 月額賃料 |
| 52 | currentStatus | Text | ❌ | 現況 |
| 53 | tochiMenseki | Dec(10,2) | ❌ | 土地面積 |
| 54 | tatemonoMenseki | Dec(10,2) | ❌ | 建物面積 |
| 55 | kouzou | Text | ❌ | 構造 |
| 56 | chikunengetsuStr | Text | ❌ | 築年月 |
| 57 | soukosu | Int | ✅ | 総戸数 |
| 58 | kanrihi | Int | ✅ | 管理費 |
| 59 | syuzenTsumitate | Int | ✅ | 修繕積立金 |
| 60 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 61 | kenpei | Int | ✅ | 建ぺい率(数値) |
| 62 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 63 | youseki | Int | ✅ | 容積率(数値) |
| 64 | setsudou | Text | ✅ | 接道 |
| 63 | chimoku | Text | ✅ | 地目 |
| 64 | youtoChiiki | Text | ✅ | 用途地域 |
| 65 | tochikenri | Text | ✅ | 土地権利 |
| 66 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 67 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 68 | propertyType | Text | ❌ | 物件種別 ("Apartment") |

---

## 6. Misawa (ミサワホーム不動産)

### 6.1 MisawaCommon (抽象基底クラス)

**継承モデル**: MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentApartment

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| 1 | propertyName | Text | ❌ | 物件名 |
| 2 | pageUrl | Char(500) | ❌ | URL |
| 3 | inputDate | Date | ❌ | 登録日 |
| 4 | inputDateTime | DateTime | ❌ | 登録日時 |
| 5 | priceStr | Text | ❌ | 価格(文字列) |
| 6 | price | Int | ❌ | 価格(数値) |
| 7 | address | Text | ❌ | 住所 |
| 8 | traffic | Text | ✅ | 交通 (生テキスト) |
| 9-48 | transfer1~5, railway1~5, station1~5, etc. | Text/Int | ✅ | 交通情報 (5路線分、TransportationMixinより) |
| 49 | tochikenri | Text | ❌ | 土地権利種類 |
| 50 | kenpei | Int | ✅ | 建ぺい率 |
| 51 | youseki | Int | ✅ | 容積率 |
| 52 | youtoChiiki | Text | ❌ | 用途地域 |
| 53 | deliveryDate | Text | ❌ | 引渡時期 |
| 54 | facilities | Text | ❌ | 設備 |
| 55 | neighborhood | Text | ❌ | 周辺施設 |
| 56 | schoolDistrict | Text | ❌ | 学区 |
| 57 | transactionType | Text | ❌ | 取引態様 |
| 58 | biko | Text | ❌ | 備考 |
| 59 | updatedAt | Date | ✅ | 更新日 |
| 60 | nextUpdateAt | Date | ✅ | 次回更新予定日 |

### 6.2 MisawaMansion

**テーブル名**: `misawa_mansion`
**継承**: MisawaCommon

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MisawaCommon の全フィールド) | - | - | 基本情報 |
| 61 | senyuMensekiStr | Text | ❌ | 専有面積(文字列) |
| 62 | senyuMenseki | Dec(7,2) | ❌ | 専有面積(数値) |
| 63 | balconyMensekiStr| Text | ✅ | バルコニー面積(文字列) |
| 64 | balconyMenseki | Dec(7,2) | ✅ | バルコニー面積(数値) |
| 65 | madori | Text | ❌ | 間取り |
| 66 | kaisu | Text | ❌ | 所在階 |
| 67 | kouzou | Text | ❌ | 建物構造 |
| 68 | chikunengetsuStr | Text | ❌ | 完成時期 |
| 69 | soukosu | Int | ✅ | 総戸数 |
| 70 | kanriKeitai | Text | ❌ | 管理形態 |
| 71 | kanriKaisya | Text | ❌ | 管理会社 |
| 72 | kanrihi | Int | ✅ | 管理費 |
| 73 | syuzenTsumitate | Int | ✅ | 修繕積立金 |
| 74 | tyusyajo | Text | ❌ | 駐車場状況 |

### 6.3 MisawaKodate

**テーブル名**: `misawa_kodate`
**継承**: MisawaCommon

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MisawaCommon の全フィールド) | - | - | 基本情報 |
| 61 | tochiMensekiStr | Text | ❌ | 土地面積(文字列) |
| 62 | tochiMenseki | Dec(8,2) | ❌ | 土地面積(数値) |
| 63 | tatemonoMensekiStr| Text | ❌ | 建物面積(文字列) |
| 64 | tatemonoMenseki | Dec(8,2) | ❌ | 建物面積(数値) |
| 65 | madori | Text | ❌ | 間取り |
| 64 | kouzou | Text | ❌ | 構造 |
| 65 | chikunengetsuStr | Text | ❌ | 完成時期 |
| 66 | kakuninBango | Text | ❌ | 建築確認番号 |
| 67 | setsudou | Text | ❌ | 接道状況 |
| 68 | privateRoadFee | Text | ❌ | 私道負担 |
| 69 | setback | Text | ❌ | セットバック |
| 70 | urbanPlanning | Text | ❌ | 都市計画 |
| 71 | tyusyajo | Text | ❌ | 駐車場台数 |

### 6.4 MisawaTochi

**テーブル名**: `misawa_tochi`
**継承**: MisawaCommon

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MisawaCommon の全フィールド) | - | - | 基本情報 |
| 61 | tochiMenseki | Dec(8,2) | ❌ | 土地面積 |
| 62 | chimoku | Text | ❌ | 地目 |
| 63 | setsudou | Text | ❌ | 接道状況 |
| 64 | buildingCondition | Text | ❌ | 建築条件 |
| 65 | urbanPlanning | Text | ❌ | 都市計画 |
| 66 | currentStatus | Text | ❌ | 現況 |

### 6.5 MisawaInvestmentApartment

**テーブル名**: `misawa_investment_apartment`
**継承**: MisawaCommon

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MisawaCommon の全フィールド) | - | - | 基本情報 |
| 61 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 62 | annualRent | Int | ❌ | 年間想定賃料 |
| 63 | monthlyRent | Int | ✅ | 月額賃料 |
| 64 | currentStatus | Text | ✅ | 現況 |
| 65 | tochiMenseki | Dec(8,2) | ❌ | 土地面積 |
| 66 | tatemonoMenseki | Dec(8,2) | ❌ | 建物面積 |
| 67 | kouzou | Text | ✅ | 構造 |
| 68 | chikunengetsuStr | Text | ✅ | 完成時期 |
| 69 | soukosu | Int | ✅ | 総戸数 |
| 70 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 71 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 72 | setsudou | Text | ✅ | 接道状況 |
| 73 | chimoku | Text | ✅ | 地目 |
| 74 | propertyType | Text | ❌ | 物件種別 ("Apartment") |

### 6.6 MisawaInvestmentKodate

**テーブル名**: `misawa_investment_kodate`
**継承**: MisawaCommon

| # | フィールド名 | 型 | NULL | 説明 |
|--:|:---|:---|:---:|:---|
| - | (MisawaCommon の全フィールド) | - | - | 基本情報 |
| 61 | grossYield | Dec(5,2) | ❌ | 表面利回り |
| 62 | annualRent | Int | ❌ | 年間想定賃料 |
| 63 | monthlyRent | Int | ✅ | 月額賃料 |
| 64 | currentStatus | Text | ✅ | 現況 |
| 65 | tochiMenseki | Dec(8,2) | ❌ | 土地面積 |
| 66 | tatemonoMenseki | Dec(8,2) | ❌ | 建物面積 |
| 67 | kouzou | Text | ✅ | 構造 |
| 68 | chikunengetsuStr | Text | ✅ | 完成時期 |
| 69 | kenpeiStr | Text | ✅ | 建ぺい率(文字列) |
| 70 | yousekiStr | Text | ✅ | 容積率(文字列) |
| 71 | setsudou | Text | ✅ | 接道状況 |
| 72 | chimoku | Text | ✅ | 地目 |
| 73 | propertyType | Text | ❌ | 物件種別 ("Kodate") |

---

## 付録: バリデーションとエラーハンドリング

### バリデーション実行タイミング
- `api.py` の `_save()` 関数内で `full_clean()` を呼び出し
- 厳格化フィールド (`null=False`) が欠損している場合、`ValidationError` が発生

### エラーログ出力内容
```
WARNING: Validation failed for property: https://example.com/property/12345
WARNING: Property name: サンプル物件
WARNING: Missing/invalid fields: landArea: This field cannot be null; buildingArea: This field cannot be null
WARNING: Skipping save for this property due to validation errors.
```

### データ保存ポリシー
- 厳格化フィールドが欠損している場合、レコードは保存されず**スキップ**されます
- これにより、不完全なデータがデータベースに混入することを防ぎます
