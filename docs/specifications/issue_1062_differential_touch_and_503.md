# 仕様書: Issue #1062 差分キャッシュ一括スキップ時の進捗更新およびサイト側 503 Service Busy 耐性

## 1. 背景と課題
1. **差分キャッシュ一括スキップ時のウォッチドッグ誤認キル (`daikyo` 等)**:
   - 全国の物件一覧を取得し、大量の物件（数千件）がキャッシュ済み（価格未変更・有効期限内）である場合、詳細ページ取得を行わずに `filter_differential_items()` 内で一括チャンクスキップ（`_batch_update_cached`）される。
   - 従来は詳細保存時や一覧ページ取得時のみ `_touch_watchdog_progress()` を呼んでいたため、180秒間詳細取得クエリが発生しないと親プロセスのウォッチドッグに「無進捗」と誤認され強制終了されていた。
2. **相手先サイトの 503 Service Unavailable 時のクラッシュ (`smtrc` 等)**:
   - `smtrc.jp` などの外部サイトが一時メンテナンスや負荷過多で HTTP 503 を返却した場合、`baseParser` では `ServerBusyException` を発生させるが、CLI エントリポイント（`main.py`）で捕捉されずプロセスが Exit Code: 1 で異常終了し、Slack に「❌ 【失敗】」が通知される。
   - 相手先サーバー過負荷・一時的利用不可（503/ServerBusy）は致命的バグではなくサイト都合のスキップ事象であるため、`ServerBusyException` を適切にハンドリングし、ジョブを安全にスキップ完了（メトリクス記録付き）させる必要がある。

## 2. 変更仕様

### 2.1 差分キャッシュ一括スキップ時の進捗更新 (`differential.py`)
- `_process_differential_chunk()` において、モデルクラス名（`model_class.__name__`）から会社名および物件種別を逆引きするヘルパー `_detect_company_and_type_from_model(model_class)` を用意。
- キャッシュ物件のスキップ更新（`_batch_update_cached`）時、定期的に `touch_crawler_progress(company, ptype)` を呼び出し、進捗ファイルの mtime を更新する。

### 2.2 一時的サーバー過負荷 (HTTP 503 / ServerBusyException) のハンドリング (`main.py`, `smtrcParser.py`)
- `smtrcParser._getContent()` において、Playwright が未セットアップの環境や相手先が全停止している場合でも `ServerBusyException` を上位に伝播する。
- `main.py` の CLI 実行ブロックにおいて、`ServerBusyException` を検知した場合は「サイト側一時過負荷（Server Busy）」として捕捉し、`FailureReporter` への記録（警告レベル）とともに、Exit Code: 0（スキップ完了）として安全に終了させる。
