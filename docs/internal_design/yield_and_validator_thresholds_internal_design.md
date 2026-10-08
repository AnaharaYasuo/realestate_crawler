# 投資物件利回り補正およびバリデーション許容境界の是正 内部設計書 (Issue #791)

## 1. モジュール改修仕様

### 1.1 `src/crawler/package/parser/baseParser.py`
`_guard_gross_yield(item: models.Model)`:
```python
@staticmethod
def _guard_gross_yield(item: models.Model) -> None:
    if not hasattr(item, 'grossYield'):
        return
    f_obj = item._meta.get_field('grossYield')
    current_yield = getattr(item, 'grossYield', None)
    if current_yield is None or (isinstance(current_yield, (int, float, Decimal)) and current_yield <= 0):
        price = getattr(item, 'price', None)
        annual_rent = getattr(item, 'annualRent', None)
        if not annual_rent and hasattr(item, 'monthlyRent') and getattr(item, 'monthlyRent', None):
            annual_rent = int(getattr(item, 'monthlyRent')) * 12
        if price and annual_rent and price > 0 and annual_rent > 0:
            calc_yield = round((float(annual_rent) / float(price)) * 100.0, 2)
            if 0 < calc_yield <= 100.0:
                setattr(item, 'grossYield', Decimal(str(calc_yield)))
                return
    if getattr(item, 'grossYield', None) is None and not f_obj.null:
        setattr(item, 'grossYield', Decimal('0.0'))
```

### 1.2 `src/crawler/package/utils/data_validator.py`
`_is_low_price_allowed(cls, item: Any, ptype: str) -> bool`:
URL文字列（`item.pageUrl` 等）に `toushi` または `invest` が含まれる場合に `True` を返却する判定を追加。

`_validate_price(cls, item: Any, ptype: str, reasons: list[str]) -> float`:
上限判定閾値を `200000.0`（20億円）から `500000.0`（50億円）に変更。
