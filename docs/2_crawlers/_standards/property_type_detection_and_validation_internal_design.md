# 内部設計書: PropertyTypeDetector 誤判定防止およびデータ整合性検証最適化

## 1. クラス・関数変更仕様

### 1.1 `PropertyTypeDetector` (`src/crawler/package/utils/property_type_detector.py`)
- **`TOCHI_KEYWORDS` 定義の改修**:
  - `TOCHI_KEYWORDS = ["売土地", "売り土地", "建築条件付土地", "売地"]`
  - 「土地」単体語を除外し、複合語・確定語に限定。
- **`_detect_rule_based` の判定順序変更**:
  1. `specs` 内の利回りシグナル（最優先）
  2. `title` からのキーワード判定
  3. `html_text` からの Yield Guard
  4. `specs` からの種別判定
  5. **`url` からの種別判定（昇格）**: URL パスに明示的な種別情報がある場合、本文全文検索より優先
  6. `html_text` からのキーワード判定
  7. フォールバック（AI または default）

### 1.2 `validate_data` (`src/crawler/scripts/maintenance/validate_data.py`)
- **直近期間フィルタの導入**:
  - `days = int(os.getenv("VALIDATE_DATA_DAYS", "7"))`
  - `if days > 0 and hasattr(model_cls, "inputDate"):`
    - `since = datetime.date.today() - datetime.timedelta(days=days)`
    - `qs = model_cls.objects.filter(inputDate__gte=since)`
  - `else: qs = model_cls.objects.all()`
- **CLI オプション対応**:
  - `--all` または `--days <int>` 引数のサポート。

## 2. データベースクレンジング
- 過去の誤ルーティングで登録された誤格納レコードの整理。
  - 例: 三井のリハウスで `/mansion/` URL を持つ `MitsuiTochi` レコード、アットホームの `buy_other` を持つ `AthomeMansion` レコードの整理。

## 3. 投資用サブ種別判定・居住用賃貸競合防止・土地キーワードクレンジング内部設計（Issue #623）

### 3.1 `TOCHI_KEYWORDS` 定義のクレンジング
- `src/crawler/package/utils/property_type_detector.py` の `TOCHI_KEYWORDS`:
  - `TOCHI_KEYWORDS = ["売土地", "売り土地", "建築条件付土地", "売地"]`
  - 「土地」単体語を完全に排除。

### 3.2 判定順序と優先度の最適化 (`_detect_rule_based`)
- 明示的な URL 種別パスがある場合、本文テキスト内の投資シグナル（「オーナーチェンジ」「賃貸中」等）に引きずられて誤判定されないよう、順序を制御：
  1. `specs` の利回りシグナル（スペック表に明示的な数値利回りがある場合は投資物件確定）
  2. `specs` の明示的種別判定（「物件種別」「種目」等）
  3. `title` からの種別判定
  4. **`url` からの種別判定**: URLに `/mansion/`, `/kodate/`, `/tochi/` 等の居住用パスがある場合は、本文の曖昧な「賃貸中」等のシグナルより優先
  5. `html_text` からの Yield Guard（URLやspecsで特定できない場合の投資シグナル検出）
  6. `html_text` からのキーワード判定
  7. フォールバック

### 3.3 投資用サブ種別判定の細分化 (`detect_investment_type`)
- `PropertyTypeDetector.detect_investment_type(text, specs=None, default="Apartment")`:
  - テキストおよびスペック表（間取り、専有面積、建物面積、構造等）から詳細なサブ種別（`"Apartment"`, `"Mansion"`, `"Kodate"`, `"Building"`）を判定：
    - 「戸建」「一戸建て」「テラスハウス」または専有面積がなく土地・建物面積のみの場合 ➔ `"Kodate"`
    - 「マンション」「レジ」または「区分」「専有面積」がある場合 ➔ `"Mansion"`
    - 「ビル」「店舗」「事務所」➔ `"Building"`
    - それ以外（「アパート」「一棟アパート」等）➔ `"Apartment"`

## 4. オートヒール異常解消・低価格物件許容・投資パーサー是正内部設計（Issue #769）

### 4.1 `PropertyDataValidator` 拡張 (`src/crawler/package/utils/data_validator.py`)
- **`_is_low_price_allowed(item, ptype)`**:
  - 地目（`chimoku`）が山林、原野、雑種地、農地、畑、田、保安林のいずれか
  - 物件名または備考に「山林」「原野」「資材置場」「持分」「オーナーチェンジ」のいずれかを含む
  - 物件種別が `tochi`、`investment`、`invest`、`investmentapartment` 等
- **価格・単価閾値の動的切り替え**:
  - `_validate_price`: `min_price_man = 1.0 if _is_low_price_allowed else 100.0`
  - `_validate_unit_price`: `min_unit = 10.0 if _is_low_price_allowed else 1000.0`

### 4.2 `TokyuParser` 改修 (`src/crawler/package/parser/tokyuParser.py`)
- **`check_tokyu_listing_ended`**:
  - `title_text` に「収益物件（建物）一覧」「投資用不動産 | 収益物件」を含む場合も `ListingEndedException` を送出。
- **`_parseGrossYield`**:
  - 正規表現マッチなし時のフォールバックを `Decimal(0)` から `None` に変更。
- **`TokyuInvestmentKodateParser._parsePropertyDetailPage`**:
  - タイトルまたは物件名に「マンション」「区分」「一室」が含まれ、かつ土地面積がない場合、または土地面積が0以下の場合は `SkipPropertyException` を送出。

### 4.3 `OdakyuParser` 改修 (`src/crawler/package/parser/odakyuParser.py`)
- **`_invest_card_traffic`**:
  - `.estate-info-list dl` から `dt: 交通` を抽出し返却。
- **`_fill_invest_card_identity`**:
  - `traffic_str` を抽出し、`item.traffic` セットおよび `_populateTraffic(item, [traffic_str])` を呼出。
- **`_apply_invest_card_field`**:
  - `dt_text` に「交通」が含まれる場合のハンドリングを追加。

## 5. 割安物件検出精度向上・種別誤判定根絶・区分マンション土地面積除外内部設計（Issue #969）

### 5.1 `PropertyTypeDetector` 改修
- **Yield Guardの区分保護**:
  - `_has_yield_signal` または `_has_yield_in_object` が真であっても、以下のいずれかを満たす場合は `apartment` ではなく `mansion` を返却：
    1. `senyuMenseki` が存在かつ有効数値
    2. `kaisuStr` / `floor` に階数表記（〇階/〇階建等）が存在
    3. タイトルまたはスペックに「区分」「一室」「号室」が含まれる
- **商業ビル・一棟ビルの戸建フォールバック防止**:
  - `_detect_from_area_fields` および `_match_keywords`:
    - タイトルやスペックに「ビル」「一棟ビル」「店舗」「事務所」を含む場合、土地＋建物面積があっても `kodate` にフォールバックさせず、`apartment`（投資/一棟）を返却。

### 5.2 区分マンションの土地面積除外 (`src/crawler/package/ml/features/`)
- `parsers.py` の `calculate_area_and_setback`:
  - `if property_type == 'mansion': tochi_area = 0.0`
  - 区分所有物件の敷地全体面積が `tochi_area` に代入されて積算価格・原価法評価がインフレするのを物理的に遮断。

### 5.3 クレンジング要フラグ保持物件の学習除外 (`src/crawler/package/ml/training/train.py` 等)
- データ取得時に `filter(price__gt=0).exclude(needs_recrawl=True).exclude(needs_parser_fix=True)` を適用。

### 5.4 誤判定テーブル格納物件の移送・クレンジング・物理削除 (`src/crawler/scripts/maintenance/cleanse_issue_969_data.py`)
- **HomesInvestmentApartmentParser.property_type の正規化**:
  - `property_type = 'apartment'` に設定し、`UrlRouter` と連動して動的種別判定 `mansion` 時に `HomesMansionParser`（`HomesMansion` テーブル）へ自動ルーティングする。
- **本番DBデータ移送スクリプト**:
  1. `homes_investment_apartment` 内の区分判定レコード（`tatemonoMensekiStr LIKE '%専有%'` または所在階あり）を特定。
  2. `homes_mansion` テーブルへ未登録のURLを対象に、属性（`propertyName`, `price`, `address`, `traffic`, `senyuMenseki`, 交通情報等）を正確にマッピングして INSERT。
  3. `property_evaluation` の `property_id` を新設 `homes_mansion.id` に更新し、`property_type = 'mansion'`、`needs_recrawl = 1`、`data_quality_issue = 'migrated_misclassified_unit_mansion'`、予測価格（`first_stage_predicted_price`, `second_stage_predicted_price`）を NULL にリセット。
  4. 移送完了後、旧テーブル `homes_investment_apartment` から旧レコードを `DELETE`。





---

## 5. 物件種別誤判定廃絶の4層防衛アーキテクチャ詳細設計 (Issue #1151)

### 5.1 4層防衛パイプライン
1. **Layer 1: DOM ノイズ除去 (`strip_dom_noise_for_detection`)**
   - `ParserBase._maybe_switch_parser` 等で HTML からテキストを抽出する際、`<header>`, `<nav>`, `<footer>`, `<aside>`, `.breadcrumb`, `.gnav`, `.sidebar`, `.recommend` 等のグローバルナビ・メニュー・他物件推薦枠を除去したメインコンテンツ領域のテキストのみを `PropertyTypeDetector.detect()` に渡す。
2. **Layer 2: 物理構造 × 収益状態の直交分離**
   - URLパスによる明示的な構造指定（`/mansion/`, `/kodate/`, `/tochi/`, `/apartment/` 等）およびページ表題（`<h1>`, `<title>`）の物理構造キーワードを最優先する。
   - 区分マンションのオーナーチェンジ物件（URLまたはスペックに区分/専有面積/バルコニー/管理費・修繕積立金が存在し、かつ利回り表記がある物件）を一棟アパート（`apartment`）に誤判定しない。
   - オフィス・店舗・倉庫・工場・駐車場・一棟ビル等の非住宅商用物件は `excluded` と判定し、居住用一棟アパート（`apartment`）への混入を遮断する。
3. **Layer 3: ラベル限定スペック判定 (`_detect_from_specs`)**
   - `specs.values()` 全体（自由記述の「備考」「PRコメント」等の「アパート用地に最適」「近隣にマンションあり」等）を無差別走査することを廃止し、`種別`・`物件種目`・`建物構造`・`間取り`・`総戸数`・`専有面積`・`土地面積` 等の明示的ラベルキーに基づき判定する。
4. **Layer 4: Post-Parse 物理不変条件ゲート (`validate_physical_invariants`)**
   - パース完了後のモデルオブジェクトに対し、物理的不変条件（例: `tochi` なのに `senyu_menseki` や `madori` が存在する、区分 `mansion` なのに `senyu_menseki` が無く `tochi_menseki` のみ存在する等）を検証し、不整合を検知・補正する。
