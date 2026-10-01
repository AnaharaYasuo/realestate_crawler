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
