# 外部設計書: クローラー巡回パイプラインにおける Executor Shutdown 例外解消 (Issue #1016)

## 1. インターフェース変更概要
- _handle_local_execution(api_url, detail_url):
  - 呼び出し元 _fetch() は wait asyncio.to_thread(...) ではなく同期呼び出し self._handle_local_execution(...) に変更。
  - 理由: _handle_local_execution 内でスレッド 	hreading.Thread(...) を立ち上げ即座にリターンするためブロッキングは皆無であり、イベントループの Executor シャットダウンの影響を完全に遮断できる。
- _save_error_html_by_url(url, model_name, reason, raw_html):
  - 	o_thread 実行時に RuntimeError が発生した場合は同期関数 _sync_save_error_html_by_url を直接呼び出す安全フォールバックを適用。
