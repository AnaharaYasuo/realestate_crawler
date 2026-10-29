# 内部設計書: クローラー巡回パイプラインにおける Executor Shutdown 例外解消 (Issue #1016)

## 1. 内部構造設計
- src/crawler/package/api/api.py:
  - _fetch メソッド内で local_result = self._handle_local_execution(api_url, detail_url) として同期実行。
  - _save_error_html_by_url メソッド内で 	ry ... await asyncio.to_thread(...) except RuntimeError: _sync_save_error_html_by_url(...) を適用。
  - ParseDetailPageAsyncBase._save_error_html_by_url でも同様のフォールバックを適用。
  - CrawlerReporter.success / CrawlerReporter.failure もイベントループ終了時に安全にフォールバック。
