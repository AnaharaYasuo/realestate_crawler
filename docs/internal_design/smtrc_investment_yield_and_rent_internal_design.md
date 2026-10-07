# smtrc 投資物件パース（現行利回り対応・年収文字列正規化）内部設計書 (Issue #775)

## 1. 詳細仕様

### 1.1 `src/crawler/package/utils/converter.py`
`parse_yen(text)` の修正：
```python
def parse_yen(text):
    """
    円単位の文字列を数値に変換する
    例: "15,760円" -> 15760
        "12,270,000円（2026年8月18日確認）" -> 12270000
    """
    if not text or text == "-":
        return None
    try:
        # "12,270,000円（2026年確認）" 等、末尾に日付や注記が含まれるケースに対応
        yen_match = re.search(r'(\d[\d,]*)\s*円', text)
        if yen_match:
            val_clean = yen_match.group(1).replace(',', '')
            if val_clean:
                return int(val_clean)
        # 数字以外の文字を除去 (フォールバック)
        val = re.sub(r'\D', '', text)
        if val:
            return int(val)
    except Exception:
        pass
    return 0
```

### 1.2 `src/crawler/package/parser/smtrcParser.py`
`SmtrcInvestmentParser._apply_invest_yield_and_rent` の修正：
```python
    @staticmethod
    def _apply_invest_yield_and_rent(item, specs: dict) -> None:
        gross_yield_str = (
            specs.get("利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("想定利回り", "")
            or specs.get("現行利回り", "")
        )
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)
        annual_rent_str = (
            specs.get("想定年間収入", "")
            or specs.get("年間想定収入", "")
            or specs.get("想定収入", "")
            or specs.get("現行年間収入", "")
        )
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12
```

### 1.3 `config/selectors/smtrc.yaml`
```yaml
investment:
  ...
  field_mappings:
    利回り: "grossYield"
    表面利回り: "grossYield"
    現行利回り: "grossYield"
    想定年間収入: "annualRent"
    年間想定収入: "annualRent"
    現況: "currentStatus"
```

### 1.4 `src/crawler/package/parser/totateParser.py`
```python
    async def parseNextPage(self, response: BeautifulSoup):
        for a in response.select(".paging a, .pager a"):
            text = a.get_text()
            if "次" in text or "next" in text.lower() or ">" in text:
                data_href = a.get("data-href")
                if data_href:
                    try:
                        decoded_qs = base64.b64decode(data_href).decode("utf-8")
                        if decoded_qs:
                            if decoded_qs.startswith("?"):
                                return self.getRootDestUrl(f"/buy/search/result/detail_search/{self.property_type or 'mansion'}/kanto/{decoded_qs}")
                            return self.getRootDestUrl(decoded_qs)
                    except Exception:
                        pass
                href = a.get("href")
                if href and not href.startswith("javascript:"):
                    return self.getRootDestUrl(href)
        return ""
```

## 2. 単体テスト仕様 (`tests/unit/test_smtrc_investment_yield_and_rent.py`)
1. **`parse_yen` 日付注記分離テスト**:
   - `parse_yen("12,270,000円（2026年8月18日確認）") == 12270000`
   - `parse_yen("18,511,800円（2026年3月27日確認）") == 18511800`
   - `parse_yen("15,760円") == 15760`
   - `parse_yen("15,760") == 15760`
2. **`SmtrcInvestmentParser` 現行利回り抽出テスト**:
   - specs に `{"現行利回り": "3.50%", "現行年間収入": "12,270,000円（2026年8月18日確認）"}` を与えたとき、`item.grossYield == Decimal("3.50")` かつ `item.annualRent == 12270000` となること。
3. **`TotateParser` 改ページ data-href デコードテスト**:
   - `data-href="P3BhZ2U9MiZzb3J0PW5ld19hcnJpdmFsJmxpbWl0PTIw"` かつ `href="javascript:;"` の改ページ要素から、復元された正しいURLが返却されること。
