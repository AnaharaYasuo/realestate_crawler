# smtrc 投資物件パース（現行利回り対応・年収文字列正規化）要件定義書 (Issue #775)

## 1. 背景と課題
- **課題1: SmtrcInvestmentParserにおける「現行利回り」未抽出によるエラーログ**
  - 三井住友トラスト不動産（smtrc）の投資用物件（`/detail/CompareDetails?propertyCode=...`）において、利回り表記として「現行利回り」（例: `現行利回り: 3.50%`）が使用されている物件がある。
  - 現在の `SmtrcInvestmentParser._apply_invest_yield_and_rent` は「利回り」「表面利回り」「想定利回り」のみを参照しており、「現行利回り」が抽出されず `grossYield` が None となり、`[PARSER_EXTRACTION_ERROR]` が発報されていた。
  - また `config/selectors/smtrc.yaml` の `investment.field_mappings` にも `現行利回り` が未登録であった。
- **課題2: 日付・注記付き年収文字列パース時の数値肥大化・クランプ異常**
  - 三井住友トラスト不動産の年収項目（`現行年間収入` 等）に `12,270,000円（2026年8月18日確認）` などの日付注記が付与されている場合がある。
  - 従来の `parse_yen(text)` は `re.sub(r'\D', '', text)` で全数字を結合していたため、`122700002026818` という巨大数値となり、32bit整数上限（2147483647）にクランプされて不正な値が保存されていた。

## 2. 機能要件 (FR)
- **FR-SMTRC-INV-001 (現行利回りの抽出対応)**:
  - `SmtrcInvestmentParser._apply_invest_yield_and_rent` において、`利回り`、`表面利回り`、`想定利回り` に加え、`現行利回り` からも `grossYield` を抽出する。
  - `config/selectors/smtrc.yaml` の `investment.field_mappings` に `現行利回り: "grossYield"` を追加する。
- **FR-CONV-001 (円単位文字列パース時の注記・日付分離)**:
  - `converter.parse_yen(text)` において、`XXX円（...）` や `XXX円(...)` のように「円」の直前に金額が存在する場合、「円」より前の金額部分の数字のみを抽出し、末尾の括弧内や注記に含まれる年・月・日の数字が混入しないようにする。

- **FR-TOTATE-001 (東京建物ページネーション data-href デコード対応)**:
  - `TotateParser.parseNextPage` において、`a[href='javascript:;']` のリンクであっても `data-href` 属性にBase64エンコードされたクエリ文字列が含まれている場合、デコードして正しい検索一覧URL（`https://sumikae.ttfuhan.co.jp/buy/search/result/detail_search/.../?page=2...`）を復元・進達できるようにする。

## 3. 非機能要件 (NFR)
- **NFR-001**: 既存の `parse_yen`、`parse_rent`、`SmtrcInvestmentParser`、`TotateParser` の単体テストおよび回帰テストに破壊的影響を与えないこと。
- **NFR-002**: 実行速度・レイテンシを劣化させず、正規表現の後戻り（ReDoS）を防止すること。
