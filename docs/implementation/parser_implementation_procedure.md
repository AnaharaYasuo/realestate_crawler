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
- **一項目一メソッド設計 (Template Method パターン)**: 1項目につき1つの専用抽出メソッド（`_parsePrice`, `_parseAddress` 等）を定義します。
- **【厳格ルール】関数名・メソッド名への漢字利用禁止規約**:
  関数名およびメソッド名に漢字（日本語文字）を使用することは固く禁止します。すべてのパースメソッド・ヘルパー関数は英字 (CamelCase / snake_case) で命名します。（例: `_parseSenyuMenseki`, `_parseMadori`, `_parseYearBuilt`）。
- **基底クラス抽象化・統一インターフェース (Template Method パターン)**:
  基底クラス (`ParserBase`) および物件種別ごとに統一された標準パース抽出メソッド群を完備します。
  - **全種別共通**: `_parsePrice`, `_parsePriceStr`, `_parseAddress`, `_parsePropertyName`, `_parseTransport1`, `_parseKenpei`, `_parseYouseki`, `_parseSetsudou`
  - **マンション固有**: `_parseBuildingArea`, `_parseMadori`, `_parseYearBuilt`, `_parseKouzou`, `_parseFloor`, `_parseSouKosu`, `_parseManagementFee`, `_parseReserveFund`
  - **戸建/土地固有**: `_parseLandArea`, `_parseBuildingArea`, `_parseRights`, `_parseYoutoChiiki`, `_parseChimoku`
  - **投資用固有**: `_parseGrossYield`, `_parseAnnualRent`




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

## パーサー実装原則と継承構造
1. **基底クラス `ParserBase` の必須継承**:
   - `package/parser/` 配下のすべての不動産パーサークラスは、例外なく `ParserBase`（またはその直系派生クラス）を継承しなければならない。
   - `ParserBase` を継承していない独立した孤立パーサークラスの作成はアーキテクチャ違反として厳禁。
2. **自動継承検証テスト (`test_all_parsers_inherit_from_parser_base`) の常駐**:
   - `test_parser_abstract_methods.py` にて `pkgutil` / `inspect` により全パーサークラスを動的探索し、`issubclass(cls, ParserBase)` を自動検証する単体テストを維持・実行すること。

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

## 7. 普遍開発ルール：TDD ＆ 動的二段階検証原則
今後行われるパーサー開発・修正・最速化リファクタリング等のいかなるコード変更においても、以下を普遍の確認ルールとして適用・徹底すること：

1. **TDD（テスト駆動開発）の徹底**:
   - コード変更前に事前検証テスト/確認スクリプトを作成・実行し、動作の安全と結果の正当性を保持しながら開発を反復（Micro-Diff）する。
2. **動的アクティブ物件検証**:
   - 古いローカルの固定ファイルには依存せず、テスト実行時に動的に「現在公開中の最新アクティブ物件生HTML」を直接取得して検証する。
3. **動的二段階件数制御（3件 ➔ 追加17件＝計20件/サイト×種別）**:
   - 全サイト×全種別に対し、まず**先頭3件**でスモーク検証（Phase 1）を実行し、問題なければ**追加17件（合計20件/サイト×種別）**へ自動拡張（Phase 2）して深層網羅性を検証する。
4. **純処理時間アサーション（1,000ms以内/件）**:
   - ネットワークHTTP通信待ち時間を完全に除外した「純粋なDOM/パース・データ処理時間」を計測し、**1件あたり1,000ms（1秒）を超過した場合はパフォーマンス劣化バグとしてテスト失敗 (FAIL)** と判定する。

## 8. 抽出結果検証 ＆ 欠損・0補完隠蔽防止エラーロギング規約 (Issue #209)
パーサーのセレクター指定ミスや画面構造変更による項目抽出漏れを早期検知・可視化するため、基底クラス `ParserBase.clean_parsed_item()` の冒頭で `validate_extracted_fields(item)` が自動実行されます。

- **検査対象フィールド（種別別）**:
  - **マンション**: `price`, `address`, `senyuMenseki`, `madori`, `chikunengetsuStr`, `kouzou`
  - **戸建**: `price`, `address`, `tochiMenseki`, `tatemonoMenseki`, `madori`, `chikunengetsuStr`, `kouzou`
  - **土地**: `price`, `address`, `tochiMenseki`
  - **投資用**: `price`, `address`, `grossYield`, `annualRent`, `kouzou`
- **検知条件**:
  - 値が `None`、空文字 `""`、または本来正数であるべき項目（面積・価格・賃料・利回り等）での `0`（`Decimal('0.0')` 含む）。
- **エラーロギング（1物件1集約・構造化ログ原則）**:
  - 複数項目の不備が検出された場合でもログは物件単位で1件に集約。
  - URL、物件名、会社名、モデル名、種別、不備件数、不備詳細（項目名、生値、判定理由、個別セレクタ）、および全セレクタ辞書（`self.selectors`）を含めた構造化JSONペイロード形式で `[PARSER_EXTRACTION_ERROR]` を記録し、0補完による欠損隠蔽を防止して調査・修復を迅速化します。



