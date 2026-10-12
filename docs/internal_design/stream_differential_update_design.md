# 中間ページ差分更新ストリーミング内部設計書 (Issue #886)

## 1. アーキテクチャ・モジュール設計
- **対象ファイル**:
  - `src/crawler/package/api/api.py`: `ParseMiddlePageAsyncBase._callApi` および `_extract_middle_page_details`
  - `src/crawler/package/api/differential.py`: `filter_differential_items` へのチャンク処理対応（または `chunk_size=200` 既定化）

## 2. 処理フロー
1. `_extract_middle_page_details` または `_callApi` において、`detail_url_list` が多数ある場合、200件単位でスライスして `filter_differential_items(chunk, model_class)` を順次実行。
2. `filter_differential_items` 内で既存物件を SELECT し、`to_skip` に入った物件（既存・価格変更なし）を即座に `_batch_update_cached(model_class, to_skip, now)` で UPDATE。
3. 200件ごとに DB が更新されるため、親プロセス（`run_all_crawlers.py`）の `update_watchdog_progress` が `updateDateTime` の増加を検知し、`last_act` を更新。
4. 全件処理後、詳細フェッチが必要な `to_fetch`（新規・価格変更）をまとめてタスク起動。

## 3. 定数仕様
- `DIFFERENTIAL_CHUNK_SIZE: int = 200`
