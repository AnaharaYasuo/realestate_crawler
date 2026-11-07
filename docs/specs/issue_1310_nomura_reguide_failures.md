# Issue #1310 仕様書: 野村不動産一覧並行度最適化およびRe-guide 403・空レスポンス耐性強化

## 1. 概要 (Overview)
日次クローリング運用において常習的に異常終了が発生していた以下の2サイトについて、根本原因の対策および観測性・耐障害性の強化を実施する。

1. **野村不動産 (nomura - mansion / kodate / tochi)**:
   - **症状**: 実行時間が約2時間を超過し、`FireAndForgetWaitTimeout`（7200秒タイムアウト）で強制終了（Exit Code 1）。
   - **原因**: 4都県（東京・神奈川・埼玉・千葉）計147エリア、12,000件以上の物件を抱える中、一覧・リストページパーサー（`ParseNomuraMansionListFuncAsync` 等）の並行度 `_getLocalPararellLimit()` / `_getCloudPararellLimit()` が `DEFAULT_PARARELL_LIMIT = 1`（直列実行）に制限されていた。
   - **対策**: WAF制約（`AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS["nomura"] = 3`）に整合させ、リスト並行度を `MIDDLE_PARARELL_LIMIT = 3` に引き上げ、探索速度を約3倍に高速化して2時間以内の完走を担保する。

2. **リガイド (reguide - investment)**:
   - **症状**: クラウド環境実行時等に所要時間18〜20秒程度で0件取得（Exit Code 0, `0 items scraped (Zero count failure)`）となりジョブ失敗。
   - **原因**:
     - `ReguideInvestmentParser._getContent` 内でリトライ時に例外を握りつぶして（`except Exception: pass`）最終的に親の `super()._getContent` へフォールバックしていたが、空レスポンスや403/503等のエラー時のログ・ステータスコード・エラーHTML退避が欠落していた。
     - `ParseMiddlePageAsyncBase` の中間ページストリーミング処理（`_process_middle_page_stream`）において、一覧からアイテムが1件も取得できなかった場合の `Zero items parsed from middle page` 警告およびエラーHTML保存（`_save_error_html_by_url`）が `_extract_middle_page_details` にのみ実装され、ストリーミング移行後に呼ばれなくなっていた。
   - **対策**:
     - `ReguideInvestmentParser._getContent` のリトライ処理に例外ログ・ステータスログを明示的に出力し、万一のWAF/403時にも原因を特定可能にする。
     - `_process_middle_page_stream` に一覧パース結果が0件の場合の警告ログおよび生HTML退避処理（`_save_error_html_by_url`）を追加し、証跡起点調査原則（Evidence-First）を機械的に適用する。

## 2. 変更仕様 (Specifications)

### 2.1 野村不動産 API 並行度設定 (`src/crawler/package/api/nomura.py`)
- `ParseNomuraMansionListFuncAsync`:
  - `_getLocalPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。
  - `_getCloudPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。
- `ParseNomuraKodateListFuncAsync`:
  - `_getLocalPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。
  - `_getCloudPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。
- `ParseNomuraTochiListFuncAsync`:
  - `_getLocalPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。
  - `_getCloudPararellLimit(self)`: `MIDDLE_PARARELL_LIMIT` (3) を返却。

### 2.2 リガイド パーサー耐障害性およびログ強化 (`src/crawler/package/parser/reguideParser.py`)
- `_getContent`:
  - 各試行での例外発生時に `logger.warning("RE-Guide fetch attempt %d failed for %s: %s", attempt + 1, url, e)` を記録。
  - ステータスコードが 200/202 以外（403, 429, 500, 502, 503 等）の際も `logger.warning` を出力。
  - 403 Forbidden 検知時は `AccessBlockedException` を明示的に送出してブロック実態をテレメトリへ伝達可能にする。

### 2.3 中間ページストリーミング 0件パース時生HTML保存 (`src/crawler/package/api/api.py`)
- `_process_middle_page_stream`:
  - ページから抽出したアイテム総数が 0 件の場合、`logger.warning("Zero items parsed from middle page: %s", current_url)` を出力。
  - `_save_error_html_by_url(current_url, self.__class__.__name__, f"Zero items parsed from middle page: {current_url}", raw_html=raw_html_content)` を実行して生HTMLとテレメトリを即時退避する。

## 3. テスト計画 (TDD & Verification)
1. `src/crawler/tests/unit/test_nomura_mansion_parallel.py`:
   - 野村不動産の各 List クラス（Mansion, Kodate, Tochi）の並行度が 3 (`MIDDLE_PARARELL_LIMIT`) であることを検証。
2. `src/crawler/tests/unit/test_crawlers_zero_count_fixes.py`:
   - RE-Guide のリトライ時のログ記録、403時の挙動を検証。
3. `src/crawler/tests/unit/test_middle_page_stream_zero_count.py`:
   - `_process_middle_page_stream` で0件パース時に `_save_error_html_by_url` が呼び出されることを検証。
4. アーキテクチャハーネス検証:
   - `pytest src/crawler/tests/unit/test_architecture_harness.py` 全件合格。
