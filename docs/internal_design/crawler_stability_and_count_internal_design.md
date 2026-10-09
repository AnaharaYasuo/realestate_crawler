# クローラー巡回安定化・動的種別集計・WAF/タイムアウト耐性強化 内部設計書 (Issues #819, #820, #821, #822)

## 1. 内部モジュール設計

### 1.1 `run_all_crawlers.py`: `get_count_for_job`
- ジョブ種別が `invest_kodate` の場合、検索ターゲットのモデルとして `invest_kodate` に加え、`investment_apartment` / `invest_apartment` も合算対象に含める。
```python
related_targets = [target]
if target in ("investkodate", "investmentkodate"):
    related_targets.extend(["investapartment", "investmentapartment"])
```
- 各対象モデルの `inputDateTime` / `updateDateTime` を集計し、合算した `(detail_cnt, skip_cnt, total_cnt)` を返す。

### 1.2 `tokyuParser.py`: `TokyuInvestmentKodateParser`
- クラス定義に明示的に以下を追加:
```python
class TokyuInvestmentKodateParser(TokyuInvestmentParser, KodateParserBase):
    property_type = 'invest_kodate'
```

### 1.3 `smtrcParser.py`: WAF / 空レスポンス検知
- `_smtrc_fetch_with_playwright` および `_getContent` において、取得バイト数が 1000 bytes 未満の場合にリトライまたは再取得を実施。
- `parsePropertyListPage` 等において、取得バイト数が不正な場合は警告ログを出力し、リトライを行う。

### 1.4 `baseParser.py` & `sumai1Parser.py`: タイムアウト制御
- `baseParser._getContent` 内で `getattr(self, 'REQUEST_TIMEOUT_SEC', 15)` を参照するようにし、`sumai1Parser.py` の `Sumai1Parser` で `REQUEST_TIMEOUT_SEC = 25` を定義。
- これにより、一般クローラーの15秒タイムアウトを維持しつつ、重いポータルや遅延の発生する sumai1 のタイムアウトを25秒に緩和。
