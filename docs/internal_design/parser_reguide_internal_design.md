# 内部設計書: RE-Guide（リガイド収益物件）パーサー

## 1. クラス設計
`src/crawler/package/parser/reguideParser.py`

- `ReguideInvestmentParser(InvestmentParserBase)`:
  - 投資用不動産Baseパーサー `InvestmentParserBase` を継承。
  - セレクタ設定 `config/selectors/reguide.yaml` を読み込み。
  - 文字コード: `utf-8` / `euc-jp` 自動判定（Chardet/meta準拠）。
  - `BASE_URL = "https://re-guide.jp"`
  - `property_type = "investment"`

## 2. 実装必須メソッド群 (INVESTMENT_MANDATORY_METHODS)
1. `_parsePrice(response, specs=None)` -> int / Decimal
2. `_parsePriceStr(response, specs=None)` -> str
3. `_parseAddress(response, specs=None)` -> str
4. `_parsePropertyName(response, specs=None)` -> str
5. `_parseTransport1(response, specs=None)` -> str
6. `_parseGrossYield(response, specs=None)` -> float / Decimal
7. `_parseAnnualRent(response, specs=None)` -> int / Decimal
8. `_parseChikunengetsu(response, specs=None)` -> date / str
9. `_parseKouzou(response, specs=None)` -> str
10. `_parseTochiMenseki(response, specs=None)` -> Decimal / None
11. `_parseTatemonoMenseki(response, specs=None)` -> Decimal / None

## 3. 一覧ページ詳細URL抽出
- メソッド: `extract_detail_urls(html_content: str) -> list[str]`
- コンテナ: `ul#result_list > li`
- リンク: `a[href^="/investment/"]` から `/investment/\d+/` を抽出・完全URL化

## 4. ページング・全件巡回設計
- `parseRootPage(response: BeautifulSoup)`:
  - 一覧ページの物件リンクから `ListItem(url=...)` を非同期ジェネレート。
- `parseNextPage(response: BeautifulSoup) -> str`:
  - ページャー: `ul.pager`
  - 現在ページ `li`（`[N]`、リンクなし）の直後の `li > a` の `href` を抽出し、次ページ絶対URL（`pager[p]=N+1`）を返す。
  - 次ページが存在しない場合（最終ページ `pager[p]=86`）は空文字 `""` を返却してクローリング終了。

