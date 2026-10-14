# クローラー自動修復・バリデーション境界是正 要件定義書 (Issue #940)

## 1. 概要
クローリング全タスク集約レポートおよび自己修復リクエスト（`[AUTO_HEAL_REQ]`）において検知されたパース異常・データ不整合（間取り欠損、投資物件の面積異常、低廉物件の誤検知）を解消し、データ整合性とクローラー自動修復の安定性を向上させる。

## 2. 目的とスコープ
* **目的**:
  1. 東急リバブル等で間取りが公式にハイフン（`-`）や未定・相談表記の物件が「必須項目欠損 (間取りが未抽出)」として誤判定されるのを防止する。
  2. 小田急不動産等の投資物件において、専有・建物面積が未記載でも利回りまたは賃料が存在する正常物件が「面積異常 (0.0㎡: 5㎡以下)」として誤判定されるのを防止する。
  3. ヘルスケアマンション、リゾート会員権、その他用地、倉庫用地等の低価格物件が価格異常として誤検知されるのを防止する。
  4. 東急戸建てパーサーで詳細ページのスペック辞書（`specs`）が各抽出メソッドへ適切に伝播されず間取りが欠損する問題を解消する。
* **スコープ**:
  - `src/crawler/package/utils/data_validator.py`
  - `src/crawler/package/parser/tokyuParser.py`
  - `src/crawler/tests/unit/test_yield_and_validator_thresholds.py`
  - ドキュメント階層の同期

## 3. 要件一覧
* **REQ-940-01**: `PropertyDataValidator._check_madori_and_age` において、間取り値がハイフン（`-`, `―`, `ー`）や `未定`・`相談` の場合、欠損エラーとせず許容すること。
* **REQ-940-02**: `PropertyDataValidator._extract_and_validate_area` において、投資物件（`ptype` に `invest` や `apartment` を含む）で有効な利回り（`grossYield > 0`）または賃料（`rent > 0` 等）が存在する場合、5㎡以下の面積異常エラーを免除すること。
* **REQ-940-03**: `PropertyDataValidator._is_low_price_allowed` の対象キーワードに「ヘルス・ケア」「ヘルスケア」「リゾート」「その他用地」「倉庫用地」「別荘地」「分譲地」「再建築不可」「借地権」を追加し、正常な低価格物件の誤検知を防止すること。
* **REQ-940-04**: `TokyuKodateParser._parsePropertyDetailPage` において、`specs = self._scrape_specs(response)` を取得し、各抽出メソッド（`_parseMadori`, `_parseTatemonoMensekiStr` 等）へ `specs` を渡してパース漏れを根絶すること。
* **REQ-940-05**: `PropertyDataValidator` の単体テストにおいて、DjangoのAppRegistry未初期化エラーを防止するため、`PropertyEvaluation` モデルのインポートを遅延インポートとすること。
