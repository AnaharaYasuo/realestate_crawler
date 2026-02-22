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
