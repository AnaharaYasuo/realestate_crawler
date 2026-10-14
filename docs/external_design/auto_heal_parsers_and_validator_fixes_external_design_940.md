# クローラー自動修復・バリデーション境界是正 外部設計書 (Issue #940)

## 1. システム構成・インターフェース仕様

### 1.1 バリデーション境界インターフェース（`PropertyDataValidator`）
- **間取り検証ルール**:
  - `_check_madori_and_age(item, reasons)`:
    - `item.madori` が `""`, `None`, `"None"`, `"nan"` の場合でも、値が `"-"`, `"―"`, `"ー"`, `"未定"`, `"相談"` に合致する場合は許容。
- **面積検証ルール**:
  - `_extract_and_validate_area(item, ptype, reasons)`:
    - `area <= 5.0` の場合、投資物件種別（`ptype` に `invest` や `apartment` を含む）かつ利回り・賃料が存在する場合はスキップ。
- **低価格許容ルール**:
  - `_is_low_price_allowed(item, ptype)`:
    - 物件名・備考にリゾート・ヘルスケア・倉庫用地・分譲地等のキーワードを含む場合、1万円以上の低価格を許容。

### 1.2 東急戸建てパーサー（`TokyuKodateParser`）
- `_parsePropertyDetailPage(item, response)`:
  - 事前に `specs = self._scrape_specs(response)` を実行し、全フィールドパーサーに `specs` を引数として伝播。
