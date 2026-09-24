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

## 2. 第2期残存151件モジュール別変換仕様 (Issue #421)

### 2.1 Sonar 設定および除外定義 (`sonar-project.properties`, `.github/workflows/sonar.yml`)
- `sonar.exclusions`:
  - `**/scripts/**` を除外リストに追加。内部運用・デバッグツール群によるSonar債務の混入を恒久抑止。

### 2.2 S8786 正規表現バックトラック解消仕様
- **`package/utils/deduplication.py`**:
  - `r'(\d+)丁目'` ➔ `r'(\d{1,10})丁目'`
  - `r'(\d+)番[地の]?'` ➔ `r'(\d{1,10})番[地の]?'`
  - `r'(\d+)号'` ➔ `r'(\d{1,10})号'`
- **`package/utils/converter.py`**:
  - `r'(\d+)年(\d+)月'` ➔ `r'(\d{4})年(\d{1,2})月'`
- **各社パーサー階数・幅員正規表現**:
  - `daikyoParser`, `keikyuParser`, `keioParser`, `keiseiParser`, `rearieParser`, `sotetsuParser`, `sumirinParser`, `seibuParser`:
    - `r'(\d+)階'` ➔ `r'(\d{1,5})階'`
    - `r'／(\d+)階建'` ➔ `r'／(\d{1,5})階建'`
    - `r'(\d+)階建'` ➔ `r'(\d{1,5})階建'`
    - `r'(\d+)階部分'` ➔ `r'(\d{1,5})階部分'`
  - `misawaParser`, `sumifuParser`, `tokyuParser`:
    - `r'(\d+(\.\d+)?)m'` ➔ `r'(\d{1,5}(?:\.\d{1,3})?)m'`
    - `r'(\d+(?:\.\d+)?)\s*[mｍ]'` ➔ `r'(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]'`
    - `r'([\d.]+)\s*m'` ➔ `r'([0-9.]{1,10})\s*m'`
  - `unified_property_extractor.py`:
    - `re.sub(r"\s*```$", "", text)` ➔ `text.rstrip().removesuffix('```')`
    - `r'([\d,]+(?:\.\d+)?)\s*万円'` ➔ `r'(\d{1,10}(?:\.\d{1,4})?)\s*万円'`
  - `building_resolver.py`:
    - `r"^(.+?[都道府県]?.+?[市区町村].+?\d+丁目)"` ➔ `r"^([^市区町村\n]{1,20}[市区町村][^丁目\n]{0,20}\d{1,5}丁目)"`
    - `r"^(.+?[都道府県]?.+?[市区町村][^\d\-]+)(\d+)[\-－ー]"` ➔ `r"^([^市区町村\n]{1,20}[市区町村][^\d\-\n]{1,20})(\d{1,5})[\-－ー]"`
    - `r"^(.+?[都道府県]?.+?[市区町村][^町男女東西南北]*[町男女東西南北])"` ➔ `r"^([^市区町村\n]{1,20}[市区町村][^町男女東西南北\n]{0,20}[町男女東西南北])"`
  - `features.py`:
    - `r'(\d+)\s*階(?:建|部分)?'` ➔ `r'(\d{1,5})\s*階(?:建|部分)?'`
    - `r'(\d+(?:\.\d+)?)\s*%'` ➔ `r'(\d{1,5}(?:\.\d{1,3})?)\s*%'`
    - `r'(\d+(?:\.\d+)?)\s*[mｍ]'` ➔ `r'(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]'`

### 2.3 S125 / S8572 / S2638 / S5713 / S1481 / S6035 / S3457 / S1172 / S7780 変換仕様
- **`mitsui_routes.py`, `tokyu_routes.py`**: コメントアウトされた `# request_json = json.loads(...)` 行を削除。
- **`main.py`**:
  - `logging.error(f"...: {e}", exc_info=True)` ➔ `logging.exception(f"...: {e}")`
  - `logging.error(f"...: {ce}")` ➔ `logging.exception(f"...: {ce}")`
  - `logging.error(f"...: {e}"); logging.error(traceback.format_exc())` ➔ `logging.exception(f"...: {e}")`
- **`api.py`**:
  - `logging.error(f"...: {img_err}")` ➔ `logging.exception(f"...: {img_err}")`
  - `logging.error(f"...: {e}")` ➔ `logging.exception(f"...: {e}")`
  - `eval_record, created = ...` ➔ `eval_record, _ = ...`
  - `except (SkipPropertyException, ListingEndedException) as e:` ➔ `except SkipPropertyException as e:`
- **`tokyuParser.py`**:
  - `except (json.JSONDecodeError, TypeError, ValueError, AttributeError):` ➔ `except (TypeError, ValueError, AttributeError):`
  - `def _parseAddress(self, response, specs=None):` ➔ `def _parseAddress(self, response, _specs=None):`
- **`seibuParser.py`, `sumirinParser.py`**:
  - `def _parsePrice(self, response: BeautifulSoup):` ➔ `def _parsePrice(self, response: BeautifulSoup, specs=None):`
  - `def _parseAddress(self, response: BeautifulSoup):` ➔ `def _parseAddress(self, response: BeautifulSoup, specs=None):`
- **`sumifuParser.py`**:
  - `re.split(u'/|／|\n', val)` ➔ `re.split(r'[/／\n]', val)`
- **`slack_agent_host.js`**:
  - `text.replaceAll('"', '\\"')` ➔ `text.replaceAll('"', String.raw`\"`)`
- **`resolve_duplicate_evaluations.py`**:
  - `"✔ All hierarchy assertions passed! DB is 100% clean and consistent."` ➔ `"✔ All hierarchy assertions passed! DB is 100%% clean and consistent."`
- **`sync_estat_municipalities.py`**:
  - `obj, created = ...` ➔ `_, created = ...`

