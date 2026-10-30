# 内部設計書: Issue #1122

## 1. 修正対象モジュール一覧
1. `src/crawler/package/parser/mitsuiParser.py`:
   - `_fallback_road_width_from_text`: 抽出した幅員 `Decimal(val)` に対し `0 < val <= 50.0` の境界値ガードを適用。
2. `src/crawler/package/models/nomura.py`:
   - `NomuraInvestmentApartment`, `NomuraInvestmentKodate`: `currentStatus = models.TextField(blank=True, default="")` に修正。
3. `src/crawler/package/parser/sumai1Parser.py`:
   - `_parse_investment_yield_and_rent`: 満室時想定収入がない場合、`genko_shunyu`（現行収入）および `genko_rimawari` を使用して `annualRent`, `monthlyRent`, `yieldRate` を設定。
4. `src/crawler/package/models/sumifu.py`:
   - `SumifuInvestmentApartment.chikunengetsu`: `models.DateField(null=True, blank=True)`
   - `SumifuKodate.chisei`: `blank=True`
   - `SumifuTochi.chisei`: `blank=True`
   - `SumifuInvestmentApartment.kouzou`: `blank=True`
5. `src/crawler/package/models/tokyu.py`:
   - `TokyuKodate.saikou`: `blank=True`
6. `src/crawler/package/utils/url_router.py`:
   - `sumikae.ttfuhan.co.jp` を `totate` パーサー（`TotateKodateParser`, `TotateTochiParser`）にマッピング。
