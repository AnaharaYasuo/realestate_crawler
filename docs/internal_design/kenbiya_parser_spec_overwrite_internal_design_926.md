# 内部設計書: 健美家パーサーにおける用語解説欄による築年月・スペック上書き破壊の防止 (Issue #926)

## 1. 内部ロジック変更詳細

### 1.1 `KenbiyaParserBase._is_excluded_spec_container` の導入
親要素の階層（ancestors）を走査し、用語解説やガイド領域に属しているかを判定するヘルパーメソッドを導入。
```python
def _is_excluded_spec_container(self, elem: Tag) -> bool:
    for parent in elem.parents:
        if not parent or not hasattr(parent, "get"):
            continue
        p_classes = " ".join(parent.get("class", []) or [])
        p_id = parent.get("id", "") or ""
        if any(k in p_classes for k in ["guide", "help", "glossary", "explanation", "box_outline"]) or "guide" in p_id:
            return True
    return False
```

### 1.2 `_parse_dl_specs` および `_parse_tr_specs` の改修
1. 各 `<dl>` または `<tr>` に対し、`_is_excluded_spec_container` を適用して用語解説領域配下の要素をスキップ。
2. スペック登録条件を `if key and cleaned_val and key not in specs:` とし、同一キーの先勝ち（正規スペック優先）を保証。

### 1.3 `_get_specs` の走査順序の最適化
`div.property` 内のスペック要素を優先して走査した上で、ページ全体のフォールバック走査を実施。

## 2. 単体テスト方針
`src/crawler/tests/unit/test_kenbiya_parser.py` に、以下のテストケースを追加：
- `test_get_specs_ignores_box_outline_glossary`: 上部に正規の「築年月: 1991年7月」、下部に `box_outline` 配下の「築年月: 建物が完成した年月を表示...」を含む HTML を与え、`specs["築年月"]` が `"1991年7月"` となり、`item.chikunengetsu` が `datetime.date(1991, 7, 1)` になることを検証。
