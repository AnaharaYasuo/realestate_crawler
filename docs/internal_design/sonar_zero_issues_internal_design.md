# 内部設計書: SonarCloudオープン課題解消実装仕様

## 1. モジュール別変換仕様

### 1.1 `src/crawler/package/utils/crawl_smoke_engine.py`
- `_discover_repros_json_details`:
  - 戻り値注釈を `-> None` に変更し、明示的 `return` なし（または `return`）に統一（S3516解消）。
  - 未使用引数 `parser`, `trust_as_detail` を `_parser`, `_trust_as_detail` に改名（S1172解消）。
  - 定数化: `HTML_PARSER = "html.parser"`, `PHFUDOUSAN_DOMAIN = "phfudousan.repros.jp"`, `HREF_A = "a[href]"`, `LIST_ENDPOINT = "/list"`（S1192解消）。

### 1.2 `src/crawler/package/api/mitsui.py`, `sumifu.py`, `tokyu.py` 等
- `_getApiKey`:
  ```python
  def _getApiKey(self):
      return os.getenv('SCRAPING_API_KEY', '')
  ```
  - 同一戻り値の不要な分岐を排除（S3516解消）。

### 1.3 `src/crawler/package/parser/baseParser.py`
- `parsePropertyListPage`:
  - 到達不能な `yield` 文を削除（S1763解消）。
- 定数化:
  - `INQUIRY_PATH = "/inquiry"`, `CONTACT_PATH = "/contact"`, `RENT_PATH = "/rent/"`, `CHINTAI_PATH = "/chintai/"`（S1192解消）。

### 1.4 `src/crawler/package/parser/` (mitsui, sumifu, misawa, nomura, tokyu)
- `_parseSoukosu` / `_parseSouKosu`:
  - `_parseSoukosu` の重複定義を削除し、基底クラス抽象メソッド `_parseSouKosu` の実装に統一（S1845解消）。
- `specs` 再代入 (S1226):
  - 対象メソッドにおいて、`specs = self._get_specs(response)` を `target_specs = specs if specs is not None else self._get_specs(response)` に置換し、後続の `specs.get(...)` を `target_specs.get(...)` に置換。
- 未使用 `specs` (S1172):
  - 引数宣言を `_specs=None` に改名。

### 1.5 正規表現 (athome, homes, misawa, mitsui, nomura, tokyu, deduplication)
- `_ATHOME_WIDTH_RE`, `_MISAWA_WIDTH_RE` 等:
  ```python
  # 変更前: r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?'
  # 変更後: r'(?:幅員|幅|道路|前面)\s*(?:約\s*)?(\d+(?:\.\d+)?)\s*[m米]?'
  ```
- `deduplication.py`:
  - `re.sub(r'[\s\u3000]+', '', address)` ➔ `re.sub(r'\s+', '', address)` (S5869)
  - `re.sub(r'(\d+)番(?:地|の)?', r'\1-', address)` ➔ `re.sub(r'(\d+)番[地の]?', r'\1-', address)` (S6035)

### 1.6 `src/crawler/routes/`
- 各 Blueprint 内の関数名:
  - `sumifuMansionStart` ➔ `sumifu_mansion_start`
  - `sumifuMansionRegionLocal` ➔ `sumifu_mansion_region_local`
  - `sumifuMansionRegion` ➔ `sumifu_mansion_region`
  - `main.py` からの呼び出し箇所を同期更新。
- 例外ログ:
  - `logging.error("Failed ..."); logging.error(traceback.format_exc())` ➔ `logging.exception("Failed ...")`

### 1.7 `src/crawler/scripts/debug_tools/show_migrations.py`
- 末尾の全角文字 `ー` を削除（S905解消）。
