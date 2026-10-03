# パーサー Getter メソッド化 内部設計書

## 1. クラス構造と詳細メソッド定義

### 1.1 `ParserBase` の共通 Getter 群
以下のメソッドを [`src/crawler/package/parser/baseParser.py`](file:///C:/Users/weare/.gemini/antigravity/worktrees/realestate_crawler/refactor_parser_getters/src/crawler/package/parser/baseParser.py) の `ParserBase` に実装する。引数はページ HTML 全体 (`response: BeautifulSoup`) のみ。

- `get_price(response) -> int | Decimal | None`
- `get_price_str(response) -> str`
- `get_address(response) -> str`
- `get_property_name(response) -> str`
- `get_transport1(response) -> str`
- `get_chidai(response) -> int | None`
- `get_chidai_str(response) -> str`
- `get_setsudou(response) -> str`:
  - 探索キー: `["接道状況", "接道", "道路の状況", "道路状況", "接道方向・幅員"]`
- `get_douro_muki(response) -> str`:
  - 探索キー: `["接道方向", "道路向き", "道路の向き", "方角"]`
  - フォールバック: `get_setsudou` のテキストから `(東|西|南|北|北東|北西|南東|南西)` を正規表現抽出
- `get_douro_kubun(response) -> str`:
  - 探索キー: `["道路区分", "道路種別", "公道・私道", "公私区分"]`
  - フォールバック: `get_setsudou` から `(公道|私道)` を抽出
- `get_douro_haba(response) -> str`:
  - 探索キー: `["道路幅員", "道路幅", "幅員"]`
  - フォールバック: `get_setsudou` から `(\d+(?:\.\d+)?)\s*[mｍ]` を抽出

### 1.2 `MansionParserBase` の追加 Getter 群
- `get_senyu_menseki_str(response) -> str`
- `get_senyu_menseki(response) -> Decimal | None`
- `get_madori(response) -> str`
- `get_chikunengetsu(response)`
- `get_chikunengetsu_str(response) -> str`
- `get_kouzou(response) -> str`
- `get_floor(response) -> int | None`
- `get_kaisu_str(response) -> str`
- `get_soukosu(response) -> int | None`
- `get_soukosu_str(response) -> str`
- `get_management_fee(response) -> int | Decimal | None`
- `get_reserve_fund(response) -> int | Decimal | None`
- `get_balcony_menseki_str(response) -> str`
- `get_balcony_menseki(response) -> Decimal | None`

### 1.3 `TochiParserBase` の追加 Getter 群
- `get_tochi_menseki_str(response) -> str`
- `get_tochi_menseki(response) -> Decimal | None`
- `get_kenpei(response) -> int | None`
- `get_kenpei_str(response) -> str`
- `get_youseki(response) -> int | None`
- `get_youseki_str(response) -> str`
- `get_chimoku(response) -> str`
- `get_rights(response) -> str`
- `get_youto_chiiki(response) -> str`
- `get_maguchi(response) -> Decimal | None`
- `get_hikiwatashi(response) -> str`
- `get_genkyo(response) -> str`
- `get_current_status(response) -> str`

### 1.4 `KodateParserBase` / `InvestmentParserBase` の Getter 群
土地・マンションと同様に、各種別特有の項目を整備。

## 2. 実装詳細とキャッシュ方針
1. `specs` は内部で `response._cached_specs` を参照。一度生成された辞書を使い回すため、多数の Getter を順次呼び出しても DOM パースの多重実行による性能劣化（NFR-001）は発生しない。呼び出し元が `specs` を引数で引き渡す必要はない。
2. 文字列表記と数値のパースは、`get_<field_name>_str` で文字列を確定させた後、`get_<field_name>` からそれを呼び出して `converter` を通す設計とし、探索ロジックの二重化を防ぐ。

```python
def get_tochi_menseki_str(self, response: BeautifulSoup) -> str:
    target_specs = self._get_specs(response)
    for key in ["土地面積", "敷地面積", "区画面積", "面積"]:
        if key in target_specs and target_specs[key]:
            return target_specs[key]
    return ""

def get_tochi_menseki(self, response: BeautifulSoup) -> Decimal | None:
    s = self.get_tochi_menseki_str(response)
    return converter.parse_menseki(s) if s else None
```
