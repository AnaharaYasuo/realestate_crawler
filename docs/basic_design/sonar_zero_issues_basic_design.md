# 基本設計書: SonarCloudオープン課題全件解消アーキテクチャ設計

## 1. 全体構造とアプローチ
全1,583件の課題を、影響度・安全度・パターン特性に応じて7つのバッチ（群）に分類し、段階的・決定論的に修正する。

```mermaid
flowchart TD
    A[SonarCloud Issues 1,583件] --> B1[Batch 1: BLOCKER 19件 & Bug 10件]
    A --> B2[Batch 2: 引数再代入 S1226 241件 & 未使用引数 S1172 138件]
    A --> B3[Batch 3: 正規表現最適化 S6353/S6035/S5869/S8786 167件]
    A --> B4[Batch 4: ログ例外ハンドリング S8572 121件]
    A --> B5[Batch 5: 関数命名規則 S1542 263件]
    A --> B6[Batch 6: 定数化 S1192 97件]
    A --> B7[Batch 7: モデル・クリーンアップ S6553/S5754/S1481等 残余課題]
    
    B1 --> V[段階的テスト検証 pytest 1,138件]
    B2 --> V
    B3 --> V
    B4 --> V
    B5 --> V
    B6 --> V
    B7 --> V
    V --> QG[SonarCloud Quality Gate PASS]
```

## 2. カテゴリ別修正方針

### 2.1 BLOCKER / 重大バグ
- **S1845（メソッド名大文字小文字重複）**:
  - `MansionParserBase` の `@abstractmethod` は `_parseSouKosu` (大文字K)。
  - `heimParser`, `mitsuiParser`, `nomuraParser`, `sumifuParser`, `tokyuParser` で混在していた `_parseSoukosu` を削除または `_parseSouKosu` に統合。
- **S3516（メソッド内同一戻り値）**:
  - `_getApiKey` 内の `if os.getenv('IS_CLOUD', ''): return ""` / `return ""` を `return os.getenv('API_KEY', '')` に統合。
- **S1763（到達不能コード）**:
  - `baseParser.py` 内の `return` 直後の `yield` を削除。
- **S905（副作用のない文）**:
  - `show_migrations.py` 末尾の全角ハイフン `ー` を削除。

### 2.2 引数再代入 (S1226) & 未使用引数 (S1172)
- 対象: `misawaParser.py`, `mitsuiParser.py`, `nomuraParser.py`, `sumifuParser.py`。
- **S1226**:
  ```python
  # 変更前
  def _parseXXX(self, response, specs=None):
      specs = self._get_specs(response)
      return specs.get(...)

  # 変更後
  def _parseXXX(self, response, specs=None):
      target_specs = specs if specs is not None else self._get_specs(response)
      return target_specs.get(...)
  ```
- **S1172**:
  - ポリモーフィックなシグネチャ `(response, specs=None)` で `specs` を参照しないメソッドは、引数名を `_specs=None` に統一し、未使用を明示。

### 2.3 正規表現最適化 (S6353, S6035, S5869, S8786)
- **S6353**: `[0-9]` ➔ `\d`
- **S6035**: `(a|b)` ➔ `[ab]`
- **S5869**: `[\s\u3000]` ➔ `\s`（Python の `\s` は全角空白 `\u3000` を包含）
- **S8786**: `\s*(?:約)?\s*` ➔ `\s*(?:約\s*)?`（Catastrophic Backtracking の抑止）

### 2.4 ログ例外ハンドリング (S8572)
- `except Exception:` 内で `logging.error(...)` + `logging.error(traceback.format_exc())` を呼んでいる箇所を、標準の `logging.exception(...)` に置き換え、スタックトレースを自動出力させる。

### 2.5 関数命名規約 (S1542)
- `routes/` 内の Flask ビュー関数を PEP 8 準拠の snake_case に統一。`main.py` 等のインポート元も整合更新。

## 3. 残存151件解消アーキテクチャ設計 (Issue #421)

```mermaid
flowchart TD
    subgraph S151[残存151件]
        R1[正規表現バックトラック S8786: 48件]
        R2[認知的複雑度 S3776: 77件]
        R3[コメントコード S125: 7件]
        R4[例外ログ S8572: 6件]
        R5[シグネチャ S2638: 4件]
        R6[例外・未使用・記法 S5713/S1481/S6035/S3457/S1172/S7780: 9件]
    end

    R1 --> A1[有限量指定子化 \\d{1,5} または 文字列分割 split]
    R2 --> A2_1[scripts/ 除外設定適正化 sonar.exclusions]
    R2 --> A2_2[コア関数早期リターン・ヘルパー抽出]
    R3 --> A3[旧コードコメント完全削除 & 自然文平易化]
    R4 --> A4[logging.exception 統一置換]
    R5 --> A5[specs=None パラメータ付与]
    R6 --> A6[冗長例外削除, _化, [ab]化, %エスケープ, String.raw]

    A1 --> TEST[全テスト検証 pytest]
    A2_1 --> TEST
    A2_2 --> TEST
    A3 --> TEST
    A4 --> TEST
    A5 --> TEST
    A6 --> TEST
    TEST --> ZERO[SonarCloud 残存オープン課題 0件]
```

### 3.1 S8786 (正規表現バックトラック) 解消設計
1. **無制限量指定子の有限長化**:
   - `\d+` ➔ `\d{1,5}` または `\d{1,10}`（階数、年、月、丁目、号、パーセント、面積）
   - `.+?` ➔ `[^市区町村]{1,20}` 等、文字クラス境界の厳格化
2. **決定論的文字列処理への移行**:
   - `re.search(r'(\d+)階', text)` ➔ `text.split("階")[0]` から数字抽出

### 3.2 S3776 (認知的複雑度) 低減設計
1. **内部ツール群の Sonar 設定適正化**:
   - `sonar-project.properties` および `.github/workflows/sonar.yml` の `sonar.exclusions` に `**/scripts/**` を明示追加。
2. **主要モジュールのリファクタリング**:
   - `main.py::execute_crawl_task`: タスク初期化・メトリクス保存を別関数へ分離。
   - `building_resolver.py::resolve_and_update`: 正規化とDB更新のパイプライン化。
   - `differential.py::filter_differential_items`: フィルタ条件判定の抽出。

### 3.3 その他ルール解消設計
- **S125**: `mitsui_routes`, `tokyu_routes` の残存 `# request_json = ...` コメントを削除。`building_resolver` や `sync_all_potentials` の docstring 内コード類似表記を平易な日本語へ修正。
- **S8572**: `main.py`, `api.py` の `logging.error(..., exc_info=True)` を `logging.exception(...)` に統一。
- **S2638**: `seibuParser`, `sumirinParser` の `_parsePrice`, `_parseAddress` に基底シグネチャ `specs=None` を追加。
- **S5713**: `tokyuParser` の `json.JSONDecodeError`（`ValueError` サブクラス）、`api.py` の `ListingEndedException`（`SkipPropertyException` サブクラス）の冗長指定を削除。
- **S1481**: `api.py:1195`, `sync_estat_municipalities.py:165` の未使用変数を `_` に変更。
- **S6035**: `sumifuParser.py` の `re.split(u'/|／|\n', val)` を `re.split(r'[/／\n]', val)` に置換。
- **S3457**: `resolve_duplicate_evaluations.py` の `100% clean` を `100%% clean` に置換。
- **S1172**: `tokyuParser.py:1085` の `_parseAddress(self, response, _specs=None)` に改名。
- **S7780**: `slack_agent_host.js` の `replaceAll('"', String.raw`\"`)` に置換。

