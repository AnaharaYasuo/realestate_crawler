# 外部設計書: クローラー巡回バックグラウンド待機と環境変数制御 (Issue #1022)

## 1. 概要
- クローラーのローカル並行実行（Fire-and-Forget）において、ルート呼び出しが安全に全バックグラウンド処理の完了を待機する設計および環境変数の仕様を定義する。

## 2. インターフェース・環境変数仕様
- `CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT`:
  - 型: `float`
  - デフォルト値: `7200.0` (2時間)
  - `0` または負数が指定された場合は、全てのアクティブスレッドが終了するまでタイムアウトなしで待機（無限待機）。
- `LOCAL_EXECUTION_WORKERS_PER_LOOP`:
  - 各イベントループに設定する独立 ThreadPoolExecutor のワーカー数（デフォルト: 10）。

## 3. エラーハンドリング・ログ
- 待機中、10秒ごとにアクティブスレッド数をログ出力（定期ハートビート）。
- 全スレッド終了時に `All fire-and-forget background threads finished successfully` を記録。
- `stop.flag` を検知した場合は直ちに待機を中断しクリーンアップ終了する。
