# Issue 1106 仕様書: 東急リバブル不整合データ インプレース直接修復（再クローリング不要化）仕様

## 1. 概要 (Overview)
Issue #1097 において東急リバブルのパーサー群（`TokyuKodateParser`, `TokyuMansionParser`, `TokyuInvestmentKodateParser`, `TokyuTochiParser` 等）がスペック辞書（`{'value': '...', 'element': ...}`）の文字列表現をモデルフィールド（`madori`, `kouzou`, `kaisuStr`, `tochikenri`, `youtoChiiki`, `chimoku` 等）に格納してしまう不具合が修正された。
しかし、PR #1100 で投入されたメンテナンススクリプト `cleanse_issue_1097_data.py` は、不整合レコードに一律で `PropertyEvaluation.needs_recrawl = True` を付与して再クローリングを待つ方針となっていた。

本仕様では、DB内に保存された辞書文字列表現から本来の値（`'value'` の中身）を直接抽出し、再クローリングを実施することなく既存DBレコードをインプレースで修復するスクリプトおよび手順を規定する。

## 2. 修復アーキテクチャ (In-place Cleansing Architecture)

### 2.1 対象テーブルおよびフィールド
- `tokyu_kodate`: `madori`, `kouzou`, `youtoChiiki`, `tochikenri`
- `tokyu_mansion`: `madori`, `kouzou`, `kaisuStr`, `tochikenri`
- `tokyu_tochi`: `chimoku`, `youtoChiiki`, `tochikenri`
- `tokyu_investment_kodate`: `madori`, `kouzou`, `youtoChiiki`, `tochikenri`

### 2.2 値抽出ロジック (`extract_value_from_dict_repr`)
1. 値が `None` または空文字の場合はそのまま。
2. 文字列が `"{'value'"` または `"{ \"value\""` 等で始まる場合:
   - 正規表現 `re.search(r"['\"]value['\"]\s*:\s*(?:'([^']*)'|\"([^\"]*)\")", val)` により抽出を試みる。
   - 正規表現でマッチしない場合、`ast.literal_eval` でパースし、辞書型であれば `d.get('value')` を取得する。
   - 取り出した値は `.strip()` し、空文字や None の場合は適切にハンドリングする。
3. すでに正常な文字列（辞書文字列表現ではない）の場合はそのまま変更しない。

### 2.3 PropertyEvaluation の修復
- 不整合が修復された物件（URL）について、`PropertyEvaluation` の以下の状態を復旧:
  - `data_quality_issue == 'tokyu_madori_dict_bug'` のレコードを対象に:
    - `needs_recrawl = False`
    - `data_quality_issue = None` (または空文字)
- これにより、MLモデル学習データローダー（`data_loader.py`）から除外されていた物件が即座に学習・推論対象として安全に復帰する。

## 3. テスト計画 (Verification Plan)
1. **単体テスト (`test_cleanse_issue_1097_data.py`)**:
   - 抽出関数 `extract_value_from_dict_repr` のテスト（シングルクォート、ダブルクォート、エスケープ、辞書以外の正常文字列など）。
   - モックDBレコードを用いたインプレース更新処理および `PropertyEvaluation` のフラグリセット検証。
2. **実行前検証 (Dry-Run)**:
   - スクリプトに `--dry-run` オプションを設け、対象レコード数と更新プレビューを安全に確認可能とする。
