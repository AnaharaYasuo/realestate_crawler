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

