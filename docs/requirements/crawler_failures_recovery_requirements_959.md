# 失敗クローラー群接続・リダイレクト・空結果・タイムアウト修復 要件定義 (Issue #959)

## 1. 概要
2026-10-16のクローリング実行において発生した複数のクローラー失敗（smtrc 4種別、tokyu 3種別、reguide 1種別、daikyo 1種別）の原因を特定し、安定巡回を回復するための要件を定める。

## 2. 背景と障害原因
1. **RE-Guide (investment)**:
   - サイト側の正規URLが `https://www.re-guide.jp/` へ301リダイレクト＋HTTP/2構成に変更されたことにより、旧 `https://re-guide.jp` への接続がタイムアウトで失敗。
2. **SMTRC (mansion / kodate / investment / tochi)**:
   - サーバー側の帯域制限や接続タイムアウト発生時、既存のPlaywrightフォールバック条件が「403 Forbidden」に限定されており、`TimeoutError` や `ServerDownException` がそのままスローされジョブが異常終了。
3. **東急リバブル (invest_kodate)**:
   - 投資用戸建てのサイト掲載件数が現在0件の際、正常な空結果にもかかわらず、メトリクス収集で一律「ZeroCountFailure（0件取得失敗）」としてジョブ失敗扱いとなる。
4. **東急リバブル (mansion / kodate) & 大京穴吹 (kodate)**:
   - 都道府県/エリア別の中間ページ巡回における過度な並行数や接続タイムアウト時のリトライの累積により、親プロセスのWatchdog（600秒沈黙監視）に引っかかりハング打ち切り（SIGKILL）が発生。

## 3. 受入基準 (Requirements)
- **REQ-959-1 (RE-Guide 正規URL化)**:
  - `REGUIDE_INVESTMENT_ROOT_URL` および `BASE_URL` を `https://www.re-guide.jp` に統一し、リダイレクト遅延および接続タイムアウトを解消すること。
- **REQ-959-2 (SMTRC タイムアウト/接続失敗時 Playwright フォールバック)**:
  - `smtrcParser._getContent` において、403だけでなく `TimeoutError`, `ServerDownException`, `LoadPropertyPageException`, `aiohttp.ClientError` 発生時にも Playwright ステルス取得へフォールバックし、全滅を回避すること。
- **REQ-959-3 (正常空結果 Empty Result の許容)**:
  - サイト側に掲載物件が0件である正常ケース（投資用戸建てなど）において、空結果フラグ `is_empty_result=True` をメトリクスに記録し、`ZeroCountFailure` ではなく正常空結果完了として扱うこと。
- **REQ-959-4 (エリア巡回タイムアウト制御)**:
  - 中間ページ・エリア探索時のリクエストタイムアウトを適切に設定し、特定エリアの遅延でジョブ全体が600秒無応答に陥ることを防止すること。
