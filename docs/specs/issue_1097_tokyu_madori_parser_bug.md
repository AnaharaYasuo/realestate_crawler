# Issue 1097 仕様書: 東急リバブルパーサーの間取り等フィールド辞書格納バグ修正および不整合データ再クローリング連携仕様

## 1. 概要 (Overview)
東急リバブル（tokyu）のパーサー群（`TokyuKodateParser`, `TokyuMansionParser`, `TokyuInvestmentKodateParser`, `TokyuTochiParser` 等）において、詳細ページ解析時にスペック情報から値を取得する際、`specs.get(...)` を直接参照することにより、`TokyuParser._scrape_specs()` で生成された内部辞書オブジェクト（`{'value': ..., 'element': ..., 'links': ..., 'row_element': ...}`）そのものが返却され、Entity のフィールド（`madori`, `kouzou`, `floorType_kai` / `kaisuStr`, `rights`, `youtoChiiki`, `chimoku` 等）に dict 型が代入されてしまう不具合が発生していた。

本仕様では、パーサーが常に正規化された文字列を返却するよう修正し、不整合が発生した既存レコードに対して `PropertyEvaluation.needs_recrawl = True` を設定して再クローリング対象化するクレンジング手順を規定する。

## 2. 根本原因と修正方針 (Root Cause & Fix Architecture)

### 2.1 パーサー側の不整合解消
- **原因**:
  - `TokyuParser._scrape_specs(response)` は、各項目キーに対して `{'value': ..., 'element': ...}` という辞書を格納する仕様。
  - `TokyuParser` 自身のヘルパー `self._get_spec_val(specs, key)` は、値が辞書であれば `val.get('value')` を、文字列であればそのまま文字列を返すよう設計されている。
  - しかし、`TokyuMansionParser`, `TokyuKodateParser`, `TokyuTochiParser`, `TokyuInvestmentKodateParser` のオーバーライドメソッド（`_parseMadori`, `_parseKouzou`, `_parseFloor`, `_parseRights`, `_parseYoutoChiiki`, `_parseChimoku` 等）で `specs.get("間取り", "")` のように直接辞書から get していたため、辞書オブジェクトそのものが返却されていた。
- **修正内容**:
  - サブクラスのオーバーライドメソッドにおいて、直接 `specs.get(...)` を行うのではなく、`self._get_spec_val(specs, key)` を使用するか、辞書から安全に `'value'` を取り出す共通メソッドを経由するよう統一する。
  - `TokyuParser._get_spec_val(specs, key)` を活用し、値が辞書の場合でも確実に文字列を取り出す。

### 2.2 既存不整合データのクレンジングと再クローリング連携 (Data Cleansing)
- **対象**:
  - `tokyu_kodate`, `tokyu_mansion`, `tokyu_tochi`, `tokyu_investment_kodate`, `tokyu_investment_apartment` のうち、間取り等に辞書文字列表現（`{'value'`）が含まれるレコード。
- **手順**:
  - クレンジングスクリプト `src/crawler/scripts/maintenance/cleanse_issue_1097_data.py` を提供。
  - 対象物件に対応する `PropertyEvaluation` レコードの以下のフラグを更新:
    - `needs_recrawl = True`
    - `data_quality_issue = 'tokyu_madori_dict_bug'`
  - これにより、MLモデル学習データ（`data_loader.py`）から即座に除外され、その後のピンポイント再クローリングバッチ（`recrawl_anomalies.py`）または通常クローラーによって自動的に正常値へ上書き修復される。

## 3. テスト計画 (Verification Plan)
1. **単体テスト (`test_tokyu_parser.py`)**:
   - `TokyuKodateParser`, `TokyuMansionParser`, `TokyuInvestmentKodateParser` に対して、`_scrape_specs` 形式の辞書構造を含む HTML / specs を入力した際、`_parseMadori`, `_parseKouzou`, `_parseFloor`, `_parseRights`, `_parseYoutoChiiki`, `_parseChimoku` が辞書ではなく `str` を返すことを検証する。
2. **クレンジングスクリプトテスト**:
   - dry-run オプションおよびフラグ更新の整合性を検証する。
3. **リグレッションテスト**:
   - `pytest src/crawler/tests/unit/test_tokyu_parser.py` 全件合格。
