# 要件定義書: クローラー巡回パイプラインにおける Executor Shutdown 例外解消 (Issue #1016)

## 1. 目的
_handle_local_execution およびエラーHTML保存処理において、イベントループ終了時やシャットダウン時に発生する RuntimeError: cannot schedule new futures after shutdown を根絶し、全サイトのクローラー巡回が安定完走できるようにする。

## 2. 要件項目
- **FR-1016-01**: _handle_local_execution を syncio.to_thread に委譲せず同期実行し、即座に HTTP 202 (FireAndForgetLocal) を返却すること。
- **FR-1016-02**: _save_error_html_by_url 等のエラーHTML保存処理において、イベントループ終了・シャットダウン時にも例外を出さず安全にフォールバックすること。
- **FR-1016-03**: 住友不動産をはじめとする全クローラーがクラッシュせず正常に完走すること。
