# 内部設計書: クローラー異常・価格推定失敗・パーサー異常解消 (Issue #999)

## 1. 変更対象ファイルと責務

### 1.1 `src/crawler/package/parser/baseParser.py`
- `_reject_non_property_url(self, url: str)`:
  - `skip_parts` に `"/support/"`, `"/mikata/"`, `"/guide/"`, `"/manual/"`, `"/column/"`, `"/list/"` を追加。
  - 非物件URLが渡された場合、即座に `SkipPropertyException` を発生させ、パーサー実行および 0 値保存を阻止する。

### 1.2 `src/crawler/package/parser/athomeParser.py`
- `_is_athome_detail_path(path: str) -> bool`:
  - パスに `"/list/"` や `/list$` が含まれる場合は直ちに `False` を返す。
- 面積抽出ロジック (`_get_specs_table` 等):
  - 「土地面積」「敷地面積」「公簿面積」「実測面積」に対応。
  - 「建物面積」「延床面積」「専有面積」に対応。

### 1.3 `src/crawler/package/parser/mitsuiParser.py`
- `_is_non_property_href`:
  - `"/support/"`, `"/mikata/"` のパターンを追加。
- `_parseTrafficLines`:
  - 改行なしで連結された複数駅/路線（例: 「JR山手線 新宿駅 徒歩5分 東京メトロ丸ノ内線 新宿三丁目駅 徒歩3分」）を正規表現で適切に分割。

### 1.4 `src/crawler/package/ml/evaluation/runner.py` / `targets.py`
- `resolve_company_and_type`:
  - `reguide` + `investment` または `homes` + `investment_apartment` の解決時に、DB テーブル名や種別マッピング（`apartment`, `investmentapartment`）とモデル側の命名規約の不整合を吸収。
  - 対象レコードが 0 件または評価データが空の場合でも、クラッシュせず `Skipped` / 警告として安全に処理を継続するガードを追加。

## 2. テスト設計
- `src/crawler/tests/unit/test_crawler_anomalies_fix_999.py`:
  - 三井サポートURL / アットホーム一覧URLが `_reject_non_property_url` で `SkipPropertyException` となること。
  - `_is_athome_detail_path` で `/list/` URLが `False` となること。
  - `athomeParser` で「敷地面積」「公簿面積」から正しく土地面積がパースされること。
  - `mitsuiParser` で交通文字列が欠損なく抽出されること。
  - `runner.py` で対象データ 0 件時やモデル種別解決時に例外でクラッシュしないこと。
