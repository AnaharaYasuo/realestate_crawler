# 投資物件利回り補正およびバリデーション許容境界の是正 外部設計書 (Issue #791)

## 1. 外部インターフェース・データフロー
データ保存・パース処理フローの中で、`clean_parsed_item` 内の `_guard_gross_yield` が実行され、利回りが補完される。

```
[HTML取得] ➔ [パーサー抽出] ➔ [_guard_gross_yield]
                                   │
                                   ├─ grossYield未設定または0?
                                   │    └─ price > 0 かつ annualRent > 0:
                                   │         grossYield = round((annualRent / price) * 100, 2)
                                   │
                                   └─ [PropertyDataValidator.validate_property]
                                        │
                                        ├─ URLに toushi/invest 包含 ➔ 1万円以上の低価格許容
                                        └─ 50億円以下 ➔ 正常価格と判定
```

## 2. バリデーション境界
* **価格下限**: 一般物件は100万円以上。低価格許容物件（山林・農地・投資ポータルURL等）は1万円以上。
* **価格上限**: 50億円超（500,000万円超）を異常値として警告。
* **利回り**: 0%以下または100%超を異常値として警告。
