# パーサー設計ガイドライン

## 設計思想：一項目一関数（One-Item-One-Method）

本プロジェクトのパーサー（`_parsePropertyDetailPage`）は、コードの可読性、保守性、およびテスト容易性を最大化するために、**「抽出する項目一つにつき、専用のメソッドを一つ作成する」**という厳格な設計思想に従います。

### ルール
1.  **項目の完全分離**:
    - 各価格、面積、間取り等のパースロジックを、`_parsePrice`, `_parseAddress`, `_parseMadori` のように個別のメソッドに記述します。
2.  **カテゴリ化の禁止**:
    - `_parseZoning` や `_parseSpecs` といった、複数の属性を一括で処理するメソッドの作成は禁止します。
3.  **呼び出しの単純化**:
    - `_parsePropertyDetailPage` は、これらの個別メソッドを順番に呼び出すだけの単純な「オーケストレーター」として機能させます。

### メリット
- **局所化**: 特定の項目のパースが失敗した場合、どのメソッドを修正すべきか即座に特定できます。
- **オーバーライドの容易性**: サブクラスで特定の項目（例：所在階）のパースロジックだけをカスタマイズすることが容易になります。
- **コードの明確化**: 各メソッドが短く（多くの場合数行〜10数行）保たれるため、ロジックの理解が容易です。

### 実装例
```python
def _parsePropertyDetailPage(self, item, response):
    item = super()._parsePropertyDetailPage(item, response)

    item.price = self._parsePrice(response)
    item.address = self._parseAddress(response)
    item.madori = self._parseMadori(response)
    # ... 他の項目も同様に呼び出す
    return item

def _parsePrice(self, response):
    specs = self._scrape_specs(response)
    priceStr = specs.get("価格", "").get("value", "") # 辞書構造に合わせて適宜取得
    return converter.parse_price(priceStr)


```

## URL分離と非物件リンクの除外原則

1. **種別分離（Property Type Isolation）**:
   - 一覧ページパーサー（`parsePropertyListPage`）は、自パーサーの物件種別（`self.property_type`）に厳密に合致するURLのみを yield すること。他種別（マンション一覧内の戸建て・土地等）や賃貸（`/chintai/`, `/rent/`）のリンクは除外する。
2. **非物件・案内リンクの即時スキップ（Non-Property Fast Skip）**:
   - 宣伝・案内・会員特典・問い合わせリンク（`/shiritai/`, `/360/building/`, `/inquiry/`, `/benefit/` 等）をパース対象から除外し、`SkipPropertyException` を送出してリトライ・エラーログ・エラーHTML保存を防止する。
3. **価格セレクターの完全性保証（Safe Price Extraction）**:
   - 価格のCSSセレクターに `.num` 単体などの数値のみを抽出するセレクターを使用してはならない（例: `5億9,900万円` の先頭数値 `5` のみを誤取得し、5万円の異常値アラートとなることを防止）。親要素（`.price`, `.item_price`）またはテーブルスペック（`specs.get("価格")`）から単位を含めて抽出すること。
