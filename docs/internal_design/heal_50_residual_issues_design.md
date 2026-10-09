# 残留50課題解消およびデータバリデーション・パーサー適正化 設計書 (Issue #794)

## 1. 外部設計

### 1.1 変更対象インターフェースと動作仕様
1. **三井・汎用パーサー (`baseParser._getValueByLabel`)**:
   - 入力: BeautifulSoup、ラベル文字列（`"交通"`, `"最寄り駅"` 等）
   - 変更内容: 走査対象タグを `['th', 'dt', 'span']` から `['th', 'dt', 'span', 'td']` に拡充。`<td>` がヘッダーセル（例: `<td class="table-header label">`）として使用されているページで、後続の `<td class="table-data content">` から確実に値を取得可能にする。
2. **東急パーサー (`tokyuParser._scrape_specs`)**:
   - 入力: BeautifulSoup
   - 変更内容: 従来のセレクター（`#propertySummarySection dl, div.m-status-table__wrapper`）に加え、ページ内のすべての `<dl>`（フォールバック）を走査。これにより、最新の SCSS モジュール構造（`index-module-scss-module__cv1pAa__detail` 配下の dl）からも全スペック（建物構造、階数、総戸数等）を漏れなく辞書化する。
3. **データバリデータ (`data_validator.py`)**:
   - `_check_investment_specs`:
     - 利回り0.0%は「未記載」とみなしエラーとしない（負数または1000%超のみエラーとする）。
   - `_validate_age`:
     - 築年数下限を1900年から1850年に緩和（明治・大正期の古民家・京町家物件の正規登録を許容）。
   - `_check_mansion_specs`:
     - 所在階の判定において、`floorType_kai`, `shozaikai`, `kaisu` が空であっても、`kaisuStr` に有効な階数情報（`地上X階` 含む）が存在する場合は許容する。

---

## 2. 内部設計

### 2.1 実装変更点
1. **`src/crawler/package/parser/baseParser.py`**:
   - `_getValueByLabel`: `soup.find_all(['th', 'dt', 'span', 'td'])` に更新。
2. **`src/crawler/package/parser/tokyuParser.py`**:
   - `_scrape_specs`: `wrappers = response.select(table_selector)` で空または不十分な場合、`response.find_all('dl')` をフォールバック走査する。
   - `_parseKaisuStr`: `specs` から `階数`, `所在階`, `所在階数` だけでなく、`specs.get("階数")` の値を確実に返却。
3. **`src/crawler/package/utils/data_validator.py`**:
   - `_check_investment_specs`:
     ```python
     if y_val < 0 or y_val > 1000.0:
         reasons.append(f"利回り異常 ({y_val:.1f}%: 0%未満または1000%超)")
     ```
   - `_validate_age`: 下限チェック `year < 1850` に緩和。
   - `_has_located_floor`: `地上X階` や `X階建` も階数情報として認めるか、`_check_mansion_specs` 内で `kaisuStr` が空でない場合は警告扱いとし致命的除外を回避。

### 2.2 自己修復・再評価スクリプト
- `src/crawler/scripts/debug_tools/resolve_50_residual_issues.py` を作成し、DB内の対象50パターン物件（SMTRC、三井、東急、HOMES、野村、住友不動産等）に対して再評価（URL生存確認・掲載終了マーク、最新パーサーでの再パース、バリデーション更新）を一括実行し、`needs_parser_fix=False` に更新する。
