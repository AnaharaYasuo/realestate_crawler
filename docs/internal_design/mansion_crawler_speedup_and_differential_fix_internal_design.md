# マンション系クローラー中間ページ並行化・WAF適正緩和および野村差分抽出修復 内部設計書 (Issue #867)

## 1. モジュール詳細設計

### 1.1 `src/crawler/package/parser/baseParser.py`
#### `_find_card_container(link)` の修正:
`_is_sub_heading` メソッドの判定を強化：
```python
@classmethod
def _is_sub_heading(cls, combined: str) -> bool:
    # item_title, bukken_name などのタイトル専用ラッパーは card とみなさない
    if any(k in combined for k in ('title', 'heading', 'name')):
        # ただし、外側の完全カードクラス（item_result, card, bukken_box）は除く
        if any(k in combined for k in ('result', 'card', 'box', 'panel', 'row', 'entry')):
            return False
        return True
    return False
```
これにより、`div.item_title` をカードコンテナとして早期リターンすることを防止し、上位の `div.item_resultsmall`（価格・面積等を含むカードコンテナ）が取得される。

### 1.2 `src/crawler/package/api/adaptive_concurrency.py`
`SITE_CONCURRENCY_CAPS`:
```python
SITE_CONCURRENCY_CAPS: ClassVar[dict[str, int]] = {
    "nomura": 3,
    "mitsui": 3,
    "smtrc": 2,
}
```

### 1.3 `src/crawler/package/api/api.py`
`ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS`:
```python
SITE_DOWNLOAD_DELAYS: ClassVar[dict[str, float]] = {
    "nomura": 0.5,
    "mitsui": 0.5,
    "smtrc": 1.0,
}
```

### 1.4 各API中間ページモジュール
- `src/crawler/package/api/mitsui.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` 定義
  - `ParseMitsuiMansionAreaFuncAsync._getLocalPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
  - `ParseMitsuiMansionStartAsync._getLocalPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
  - `ParseMitsuiTochi*`, `ParseMitsuiKodate*` の中間ページも同様に `MIDDLE_PARARELL_LIMIT` に更新。
- `src/crawler/package/api/nomura.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` 定義
  - `ParseNomuraMansionAreaFuncAsync`, `ParseNomuraMansionRegionFuncAsync` に適用。
  - `ParseNomuraKodate*`, `ParseNomuraTochi*` も同様。
- `src/crawler/package/api/sumifu.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` 定義
  - `ParseSumifuMansionAreaFuncAsync`, `ParseSumifuMansionRegionFuncAsync` に適用。
- `src/crawler/package/api/tokyu.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` 定義
  - `ParseTokyuMansionAreaFuncAsync`, `ParseTokyuMansionStartAsync` に適用。
