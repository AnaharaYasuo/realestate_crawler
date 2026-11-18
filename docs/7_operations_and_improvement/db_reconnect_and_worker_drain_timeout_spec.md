# Issue #1579: 差分クエリのDB切断(MySQL 2013)自動再接続および完了待機ワーカータイムアウト適正化 仕様書

## 1. 概要 (Overview)
クローリング実行において、以下の2点の異常終了パターンが発生していた。
1. **差分チェック時の DB 切断 (MySQL 2013 / 2006)**:
   長時間の Playwright 探索等でアイドル状態となった DB コネクションに対して差分クエリ（`_query_existing_records_sync`）を実行した際、ProxySQL または Cloud SQL のアイドルタイムアウトにより `django.db.utils.OperationalError: (2013, 'Lost connection to server during query')` が発生し、プロセス全体がクラッシュ（Exit Code: 1）する。
2. **完了待機ワーカータイムアウトによる 2 時間（7200秒）ハング**:
   全物件のクロール・DB保存がほぼ完了した後の最終待機処理（`_wait_for_active_fire_and_forget_threads`）において、残存 1〜2 本の Future/Thread がネットワーク待ちや Playwright ナビゲーション等でスタックした際、固定の 7200 秒（2時間）までブロックされ、親プロセスが `TimeoutError`（Exit Code 1 / hung_timeout）で異常終了する。

本仕様書は、上記2点に対する自動復旧機構および安全なタイムアウトドレイン機構を定義する。

---

## 2. 差分クエリ DB 自動再接続仕様 (DB Auto-Reconnect on Query)

### 2.1 対象箇所
- `src/crawler/package/api/differential.py`
  - `_query_existing_records_sync(model_class, urls)`

### 2.2 再接続・リトライロジック
- `_query_existing_records_sync` の実行処理を保護し、`django.db.OperationalError` や `django.db.DatabaseError` が発生した際、エラーメッセージに `2013`, `2006`, `lost connection`, `server has gone away` 等の一時切断コードが含まれているかを判定。
- 一時切断と判定された場合：
  1. `django.db.connection.close()` を呼び出して切断された既存コネクションを破棄。
  2. 警告ログを出力（`[Differential Crawl] DB connection lost (MySQL 2013/2006). Reconnecting and retrying once...`）。
  3. 1 回のみ同一クエリを再試行する。
  4. 再試行でも失敗した場合は、原則 1.1 に則り例外を再送出（安全のためフルクロールへのフォールバックは禁止）。

---

## 3. 完了待機ワーカータイムアウト適正化仕様 (Adaptive Worker Drain Timeout)

### 3.1 対象箇所
- `src/crawler/package/api/api.py`
  - `_get_fire_and_forget_drain_timeout()`
  - `_wait_for_active_fire_and_forget_threads(timeout=None)`

### 3.2 ドレインタイムアウト設計
- 通常時の最大待機時間は環境変数 `CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT`（デフォルト 7200.0 秒）とする。
- 新たに **ドレイン待機タイムアウト** `CRAWLER_FIRE_AND_FORGET_DRAIN_TIMEOUT`（デフォルト **300.0 秒 / 5分**）を導入する。
  - 親プロセス（キュー投入側）の探索処理が全て終了し、未完了の残存ワーカー数が設定値以下（例: `len(alive) <= 5` かつ進捗が一定時間変化しない場合、または残存数が減少しないまま `DRAIN_TIMEOUT` 秒経過した場合）に、不要な 2 時間のスタックを防止して未開始タスクをキャンセルし、安全に終了させる。
  - これにより、1,700件等の大量データ保存が完了した後の極小数のスタックによるジョブ全体の異常終了・2時間遅延を撲滅する。

---

## 4. テスト計画 (TDD)
1. `src/crawler/tests/unit/test_differential_db_reconnect_1579.py`:
   - `_query_existing_records_sync` が最初の実行で `OperationalError(2013, 'Lost connection')` を発生させた際、`connection.close()` が呼ばれ、再試行されて正常な結果が返ること。
   - 2 回連続で失敗した場合は `OperationalError` が再送出されること。
2. `src/crawler/tests/unit/test_fire_and_forget_drain_timeout_1579.py`:
   - ドレインタイムアウト設定値の読み取りテスト。
   - 残存タスクがスタックした場合に、長時間の 7200 秒ではなくドレイン猶予時間で安全に終了すること。
