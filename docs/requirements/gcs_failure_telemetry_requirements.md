# GCSリアルタイム障害テレメトリ・一括オートヒール要件定義書 (Issue #466)

## 1. 背景と課題
- Cloud Run Jobs はエフェメラル環境であり、コンテナインスタンスの終了や異常停止（OOMKilled、SIGKILL、Timeout）に伴いローカルファイル（`logs/` や `docs/error_pages/`）はすべて消失する。
- 複数インスタンス（Task Array: Task 0〜7）による分散クローリング実行時、各タスクのログが Cloud Logging やコンソール上で混在し、どのタスクでどの物件がなぜ失敗したかの特定に多大な調査コストを要していた。
- 障害発生時に開発者が1サイトずつ手動でエラー内容・生HTML・スタックトレースを収集し、AIエージェント（Antigravity）へ個別入力する手動運用は高負荷であり、全障害をリアルタイム永続化し、人間を介さずSlack経由でAntigravityへ自動流し込み・完全無人一括修復（ゼロタッチ Auto-Heal）できる基盤が不可欠である。

## 2. システム要件

### REQ-001: リアルタイム障害テレメトリの即時GCS永続化
- クローリングジョブの異常（HTTP 403ブロック、DOMセレクタ変更によるパース失敗、0件取得、未捕捉例外クラッシュ）を検知した瞬間、バッチ全体の終了を待たずに GCS バケット（環境変数 `STORAGE_BUCKET`）へ障害メタデータ JSON および失敗時の生 HTML を即時出力しなければならない。
- 保存パス規則:
  - 障害メタデータ: `runs/{YYYYMMDD}/failures/{company}_{property_type}.json`
  - 失敗生HTML: `runs/{YYYYMMDD}/error_pages/{company}_{property_type}/{url_hash}.html`

### REQ-002: 分散タスク（Task Array）アトミック書き込み
- 複数の Cloud Run タスク（Task 0〜7）が並行して稼働する場合でも、ジョブ単位（`{company}_{property_type}`）でファイル名を完全分離し、ロック競合や上書き破壊を発生させずにアトミックに保存できること。

### REQ-003: main.py 例外終了コードの適正化
- `main.py` CLI 実行時の未捕捉例外は `sys.exit(0)` で握りつぶさず、必ず `sys.exit(1)` 等の非ゼロ終了コードで終了し、例外詳細が親プロセスに正しく伝播すること。

### REQ-004: Antigravity用一括回収インターフェース
- 指定日付（または直近実行）の全分散タスク障害情報を、単一のコマンドまたはAPI（`fetch_run_failures.py`）により 1 回で全件集約・JSONロードできること。
- ロードされたデータには、失敗企業名・種別、失敗URL、エラー型、スタックトレース、GCS生HTMLパス、修正対象パーサーファイルパスが含まれること。

### REQ-005: Slack レポートへの一括修復コマンド自動付与
- クローリング実行完了通知（または異常アラート）の末尾に、失敗ジョブ数とともに Antigravity 一括修復用のワンライナーコマンド（または GCS パス）を自動記載すること。

### REQ-006: Slack DevAgent ゼロタッチ自動修復トリガー
- クローリングバッチ完了時に異常終了したジョブが1件以上存在する場合、人間を介さず `#dev-agent` チャンネル宛に自動修復リクエスト（`@DevAgent` メンション）を自動投稿すること。
- これにより常駐する Antigravity Bot が自動起動し、完全無人（ゼロタッチ）で GCS から障害情報を取得し、コード修正・テスト検証・PR作成までを自律完結できること。

### REQ-007: GCS ネイティブストレージバックエンド対応 (Issue #477)
- `STORAGE_BACKEND="gcs"` または `IS_CLOUD="true"` の場合、`ObjectStorageManager` は MinIO (boto3) ではなく `google-cloud-storage` (`google.cloud.storage.Client`) を直接使用し、Cloud Run のサービスアカウント権限 (ADC) で GCS バケットへアップロード・一覧・読込を実行しなければならない。
- ローカル環境 (`STORAGE_BACKEND!="gcs"`) では既存の MinIO (boto3) 動作との後方互換性を 100% 維持すること。

### REQ-008: パースエラー時生 HTML のインメモリ直接永続化 (Issue #477)
- パース例外・異常検知時、すでに手元に存在する生 HTML バイト列／文字列を `FailureReporter` および `_sync_save_error_html_by_url` に直接引き渡し、相手サーバーへの再 HTTP リクエスト (`requests.get`) を全廃すること。
- これにより、相手サーバーが 403 ブロックや連続タイムアウト状態であっても、エラー発生時の生 HTML を 100% 確実に GCS へ保存でき、かつ無駄な HTTP リクエストによる遅延を根絶すること。
- 接続タイムアウト等で生 HTML 自体が存在しない場合でも例外を握りつぶし、メタデータ JSON のみを安全に保存できること。
