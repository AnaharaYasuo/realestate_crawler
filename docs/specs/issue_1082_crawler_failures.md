# 仕様書: Issue #1082 クローリング障害是正・ハング誤判定根絶・503メンテナンススキップ・Misawa SSL修復

## 1. 概要
2026-10-22夜〜10-23未明の全体クローリング実行において検知された47件の異常事象について、根本原因を恒久的に修復する。

## 2. 課題と改修方針

### 2.1 ハング誤判定の根絶 (Watchdog & Progress Heartbeat)
- **課題**:
  - `run_all_crawlers.py` のウォッチドッグにおいて、全件 `COUNT(*)` 負荷軽減のため DB 件数増分監視が無効化（`count_fn=None`）された。
  - その結果、進捗ファイル（`.touch`）の更新間隔のみに依存するようになり、大量物件サイト（三井・野村・大京）が詳細ページパース完了待ち（`_wait_for_active_fire_and_forget_threads`）中やキュー待機中に 600 秒間更新が空き、正常稼働中（7,000件以上取得中）にもかかわらず SIGKILL される事象が発生。
- **改修方針**:
  1. `_wait_for_active_fire_and_forget_threads` 待機ループ内で、アクティブスレッドが存在する間は定期的に `touch_crawler_progress()` を呼び出し、親プロセスへ生存信号を発行する。
  2. `_detail_worker` 内での詳細ページ処理完了時および `ParseDetailPageAsyncBase._afterRunProc` 時にも進捗を touch する。
  3. `crawler_watchdog.py` において、`COUNT(*)` によるフルスキャンではなく、直近に更新されたレコードが存在するかを超軽量に確認するインデックス付きクエリ（または進捗ハートビート併用）の安全化。

### 2.2 相手先一時過負荷・深夜メンテナンス (HTTP 503 / ServerBusyException) のスキップ正常化
- **課題**:
  - `odakyu`, `keisei`, `keikyu`, `sekisui`, `daiwa` などのサイトが深夜メンテナンスまたは一時過負荷で HTTP 503 を返却した際、`baseParser` は `ServerBusyException` を送出する。
  - しかし `main.py` および `run_all_crawlers.py` では `is_empty_result=False` のまま 0 件取得となり、`ZeroCountFailure`（重大障害）としてアラート発報されていた。
- **改修方針**:
  - `main.py` の例外ハンドリングにおいて、`ServerBusyException` 受信時は「一時的サーバー混雑・メンテナンス（ServerBusy）」として捕捉し、`is_server_busy=True` をメトリクスおよびテレメトリに記録。
  - `run_all_crawlers.py` はこれを検知した場合、システムエラーではなく「⚠️ 【スキップ: メンテナンス/サーバー混雑】」として終了コード 0 の安全なスキップ扱いに分類する。

### 2.3 Misawa の SSL ハンドシェイク失敗修復
- **課題**:
  - `realestate.misawa.co.jp` への接続時、`[SSL: SSLV3_ALERT_HANDSHAKE_FAILURE]` が発生して一覧ページ取得が即座に失敗。
- **改修方針**:
  - `misawaParser.py` および Misawa API の TCPConnector において、レガシー暗号スイートを許容する `DEFAULT@SECLEVEL=1` の SSLContext を適用する。

### 2.4 オブジェクトストレージ（MinIO / GCS）未到達時の安全フォールバック
- **課題**:
  - ローカル実行や MinIO コンテナ未稼働時に、`FailureReporter` が S3 エンドポイント接続エラー（Botocore EndpointConnectionError）で長時間リトライ・ハングする。
- **改修方針**:
  - エンドポイント接続エラー時は即座にローカル fallback ディレクトリ（`logs/runs/...`）へ退避し、ブロッキングを防止。
