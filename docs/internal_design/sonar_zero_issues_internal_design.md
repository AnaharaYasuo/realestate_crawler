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

## 3. 第3期最終13件モジュール別詳細変換仕様 (Issue #428)

### 3.1 `src/crawler/package/utils/building_resolver.py` (S125)
- モジュール冒頭の docstring ブロック（`"""建物名寄せおよびマスタ解決リゾルバ..."""`）を削除。

### 3.2 `src/crawler/package/parser/tokyuParser.py` (S3776)
- `_scrape_row_dt_dd`: 行抽出処理を `_extract_specs_from_row(self, tr, header_selector, value_selector, specs)` へ抽出し、二重ループを1重ループへ平坦化。

### 3.3 `src/crawler/package/parser/mitsuiParser.py` (S3776)
- `_parsePropertyDetailPage`: 動的委譲ディスパッチ判定ブロックを `_delegate_shumoku_parser(self, item, response)` へ抽出し、主メソッドの複雑度を1に低減。

### 3.4 `src/crawler/package/parser/misawaParser.py` (S3776)
- `_getTrafficField`: バス関連フィールドの取得処理を `_extract_bus_field(self, field_to_get, walk_access, default)` へ抽出し、`elif` 連鎖を解消。

### 3.5 `src/crawler/package/parser/nomuraParser.py` (S3776)
- `_getTrafficField`: `_extract_bus_field(self, field_to_get, line, default_val)` および `_extract_railway_walk(self, field_to_get, line, default_val)` を抽出し、複雑度26を低減。

### 3.6 `src/crawler/package/parser/baseParser.py` (S3776)
- `_parseMaguchi`: 間口正規表現・Decimal変換処理を `@staticmethod def _extract_maguchi_decimal(val: str) -> Decimal | None` へ抽出。

### 3.7 `src/crawler/package/parser/homesParser.py` (S3776)
- `_parsePropertyDetailPage`: セレクターまたはヘッダー探索とテキスト抽出を共通化する `_get_table_text(self, response, selector, headers)` を導入し、重複する三項演算子と分岐を排除。

### 3.8 `src/crawler/package/ml/train.py` (S3776)
- `_extract_unit_price_record`: 面積決定ロジックを `_determine_eval_area(p, ptype: str) -> float` へ抽出。
- `_generate_single_dummy_record`: 面積サンプリングを `_sample_dummy_areas(ptype, rng)`、種別固有属性解決を `_resolve_dummy_type_attributes(ptype, area, rng)` へ抽出。
- `main`: 物件種別ごとのモデル学習・保存ループを `_train_single_ptype_models` へ抽出。

### 3.9 `src/crawler/package/ml/predict.py` (S3776)
- `_serialize_property`: 内部関数 `_val`, `_to_float` をモジュール関数 `_prop_val`, `_prop_to_float` に昇格し、`_serialize_chikunengetsu_field`, `_serialize_type_specific_fields` を抽出。

### 3.10 `src/crawler/package/ml/investment_evaluator.py` (S3776)
- `parse_chikunen`: 関数内インライン `import re` を削除し、元号別年数計算を `_parse_era_year(chikunen_str, current_year)` へループ処理化して抽出。

### 3.11 `src/crawler/package/utils/plot_shape_analyzer.py` (S3776)
- `analyze_plot_shape`: 接道・奥行推定を `_estimate_frontage_and_depth`、内接矩形・うなぎ判定を `_calculate_mir_and_unagi` へ抽出。

## 4. 第4期: Strict Quality Gate ＆ 多層防御モジュール詳細設計 (Issue #436)

### 4.1 Strict Quality Gate プロビジョニング (`src/crawler/scripts/debug_tools/setup_strict_quality_gate.py`)
1. **API 仕様**:
   - `GET /api/qualitygates/list?organization={org}`: 既存Quality Gate一覧を取得。
   - `POST /api/qualitygates/create?name=Strict+Gate&organization={org}`: ゲートが存在しない場合に新規作成。
   - `POST /api/qualitygates/create_condition`:
     - `new_violations GT 0` (新規課題が1件でもあればエラー)
     - `new_reliability_rating GT 1`
     - `new_security_rating GT 1`
     - `new_maintainability_rating GT 1`
     - `new_duplicated_lines_density GT 3`
     - `new_security_hotspots_reviewed LT 100`
   - カバレッジ指標（`new_coverage`, `branch_coverage`）は一切追加しない。
   - `POST /api/qualitygates/select?projectKey={project}&gateId={gate_id}&organization={org}`: プロジェクトに Strictly 適用。
2. **引数インターフェース**:
   - `--token`: SonarCloud Token（環境変数 `SONAR_TOKEN` 対応）
   - `--org`: `anaharayasuo`
   - `--project`: `AnaharaYasuo_realestate_crawler`
   - `--dry-run`: 変更を行わず計画のみ出力

### 4.2 CIレベル Issue 厳格アサーション (`src/crawler/scripts/debug_tools/check_sonar_remote.py`)
1. **追加オプション**:
   - `--strict-zero-issues`: スキャン完了後、PRまたはブランチの未解決Issue数が0件でない場合、詳細ログを出力して `sys.exit(1)` で終了する。
2. **終了コード規定**:
   - `0`: Quality Gate PASS かつ 未解決Issue 0件。
   - `1`: Quality Gate FAIL、または未解決Issue >= 1件、またはAPIエラー。

### 4.3 CI ワークフロー改修 (`.github/workflows/sonar.yml`)
1. **Quality Gate プロビジョニングステップ**:
   - 旧「Ensure Sonar way Quality Gate」を `setup_strict_quality_gate.py` 実行へ刷新。
2. **Quality Gate スキャンステップ**:
   - `-Dsonar.qualitygate.wait=true` を維持し、SonarCloud 側の Strict Gate 判定で即座にFAIL。
3. **CI 多層防御ステップ**:
   - スキャン後に `check_sonar_remote.py --strict-zero-issues` を実行し、万が一のすり抜けを完全遮断。

### 4.4 残存 Issue 解消 (`src/crawler/package/utils/gcp_resources.py`)
- line 356: `logger.error(f"Cloud SQL status check failed: {e}")` を `logger.exception(f"Cloud SQL status check failed: {e}")` へ変更。

## 5. 第5期: gcp_resources 認知的複雑度低減詳細設計 (Issue #442)

### 5.1 モジュール構成と責務分離 (`src/crawler/package/utils/gcp_resources.py`)

1. **`_is_prefix_matched(name: str, prefix: str) -> bool`**:
   - 単機能のプレフィックス一致判定（完全一致 または `<prefix>-` で始まるか）。
   - 認知的複雑度: 1。

2. **`_evaluate_sql_instances_matches(all_matches: list[dict], prefix: str) -> tuple[bool, str]`**:
   - 抽出されたインスタンスリストの件数（1件、複数件、0件）に応じた状態判定とログ出力。
   - 1件: `inst['state'] == 'RUNNABLE', inst['state']`
   - 複数件: `False, 'MULTIPLE_MATCHES'`
   - 0件: `False, 'HTTP 404'`
   - 認知的複雑度: 2。

3. **`_fetch_cloud_sql_instances_by_prefix(project: str, prefix: str, token: str) -> tuple[list[dict] | None, str | None]`**:
   - Cloud SQL Admin API のページネーションループ (`pageToken`) および HTTP 応答処理。
   - 各インスタンス名に対し `_is_prefix_matched` を適用して合致したものをリストへ蓄積。
   - 認知的複雑度: 12。

4. **`_find_cloud_sql_by_prefix(project: str, prefix: str, token: str) -> tuple[bool, str]`**:
   - メインエントリポイント。
   - `_fetch_cloud_sql_instances_by_prefix` を呼び出し、エラーがあれば即時返却。
   - 取得結果を `_evaluate_sql_instances_matches` へ渡して結果を返却。
   - 例外発生時は `logger.warning` 出力し `False, str(e)` を返却。
   - 認知的複雑度: 2。




