# パーサー作成手順ガイドライン

本プロジェクトにおけるパーサー開発の標準的な手順とルールを定義します。

## 1. モデルの定義・確認
実装を開始する前に、対象物件種のモデル（`package/models/*.py`）が以下の規則に従っているか確認します。

- **Str/数値のペア保持**: 面積、比率、費用、戸数などの数値項目は、必ず以下のペアで定義します。
    - `fieldnameStr`: 画面上の文字列そのまま（例: `3,000万円`, `55.20m2`）
    - `fieldname`: パース後の数値（例: `30000000`, `55.20`）
- **共通フィールド名の使用**: [database_schema.md](../internal_design/database_schema.md) の統一フィールド名リストに従います。

## 2. パーサーの基本設定
対象サイトのベースクラス（`SumifuParser`, `MitsuiParser` など）を継承してクラスを作成します。

```python
class SiteMansionParser(SiteParser):
    property_type = 'mansion'
    
    def createEntity(self):
        from package.models.site import SiteMansion
        return SiteMansion()
```

## 3. オーケストレーターの実装
`_parsePropertyDetailPage` メソッドを実装し、各項目の抽出メソッドを呼び出します。

### ルール
- **代入形式の統一**: `item.field = self._parseField(response)` の形式で記述します。
- **一項目一関数**: 複数の項目を一つのメソッドで抽出することは禁止です。

```python
def _parsePropertyDetailPage(self, item, response):
    item = super()._parsePropertyDetailPage(item, response)
    
    item.priceStr = self._parsePriceStr(response)
    item.price = self._parsePrice(response)
    # ...
    return item
```

## 4. 個別項目の抽出メソッド実装（ラベル起点戦略）

### 基本戦略
- **ラベル起点抽出**: 要素を特定するときには画面に表示されている項目名を拠り所とします。具体的にはラベルとして項目名を表示している要素を探し、そのラベルを起点に実際のデータを表示している項目を探します。
- **同一フィールド名の使用**: サイトが異なっていても、同じ情報を保持する項目は、モデル定義およびパーサー実装において必ず同一のフィールド名を使用します。詳細は [フィールド名統一規約](../internal_design/field_naming_standards.md) を参照してください。

### 重要：欠損情報とフォールバックの扱い
- **安易なフォールバック禁止**: 情報が取得できない場合のフォールバック処理（デフォルト値のセットや、モデル等での空白・null許容など）を安易に行わないでください。
- **厳格な保存**: 重要項目（所在地、価格、面積、間取り等）において、パースエラーを隠蔽するためにモデルに `blank=True` や `null=True` を追加して保存を強行することは禁止です。
- **事前の徹底確認**: フォールバックを記述する前に、該当ページ上に対象の情報が本当に記載されていないか入念にチェックし、取得漏れ（セレクタの誤り等）を隠蔽していないことを確認してください。

### 実装パターン
1. `_get_specs(response)` で取得した辞書（テーブルデータ）を利用する。
2. ラベル名で検索するユーティリティ（`_getValueByLabel` 等）を利用する。

```python
def _parseSenyuMensekiStr(self, response):
    specs = self._get_specs(response)
    return specs.get("専有面積", "")

def _parseSenyuMenseki(self, response):
    menseki_str = self._parseSenyuMensekiStr(response)
    return converter.parse_menseki(menseki_str)
```

## 5. 開発・検証プロセス（イテレーション）
パーサーの開発・修正は、以下のリサーチと実機検証のサイクルを繰り返すことで品質を担保します。

1. **エラーHTML検証**: `src/crawler/tests/error_pages` に保存されている過去の失敗HTMLに対し、修正後のコードで正しくパースできるかを確認。
2. **実機（API）検証**: 実際のサイトに対し API を実行し、ログにエラーが出ないかを確認。
3. **エラー再現HTMLの保存**: 実機検証でパースエラー、通信エラー等が発生した場合は、必ずその物件ページを `src/crawler/tests/error_pages` に検証用HTMLとして保存する。
4. **再修正**: 保存したHTMLを元にパーサーを修正し、ステップ1に戻る。

このサイクルをエラーが完全になくなるまで繰り返します。

## 6. 最終確認
全件エラーが解消されたら、以下のスクリプトで最終確認を行います。
- `verify_parsers.py`: 全サンプルのパース確認。
- `verify_db_persistence.py`: DBへの正常保存確認。
