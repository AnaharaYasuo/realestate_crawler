# 基本設計書: ログ出力改善・TRACE/DEBUG階層およびレベル付与制御 (Issue #783)

## 1. ログレベル設計と階層構造

| レベル名 | 数値 (Level No) | 標準logging / structlog メソッド | Cloud Logging Severity | 用途・出力内容 |
| :--- | :--- | :--- | :--- | :--- |
| **TRACE** | 5 | `logger.trace()` / `logging.trace()` | `DEBUG` | XPath/CSSセレクター解決文字列、微小DOM探索、次ページURL探索ループ等の超詳細追跡 |
| **DEBUG** | 10 | `logger.debug()` / `logging.debug()` | `DEBUG` | 個別物件URLマッチング、APIリクエスト/レスポンス、掲載終了判定、単一物件のパース開始/終了 |
| **INFO** | 20 | `logger.info()` / `logging.info()` | `INFO` | ジョブ全体の開始・終了、処理件数サマリー、バッチ進捗、Slack通知送信 |
| **WARNING** | 30 | `logger.warning()` / `logging.warning()` | `WARNING` | リトライ可能な一時通信エラー、429 Backoff、フォールバック発動 |
| **ERROR** | 40 | `logger.error()` / `logging.error()` | `ERROR` | パース例外、DB保存失敗、異常終了。スタックトレース内包 |
| **CRITICAL** | 50 | `logger.critical()` / `logging.critical()` | `CRITICAL` | プロセス強制終了、インフラ接続完全不達 |

## 2. ログレベル未付与の抑止設計
1. **print 文の全廃**: プロダクションコード（`src/crawler/main.py`, `src/crawler/package/api/api.py` 等）に残存していた `print()` を `logger.info()` / `logger.error()` に置換。
2. **静的検証・ルール強制**: CIおよびローカル検証において、`package/` および `main.py` 配下での `print(` 直呼び出しを禁止する。

## 3. Google Cloud Logging 連携設計
- `add_gcp_cloud_logging_fields` プロセッサにおいて、`TRACE` レベルが入力された場合は `severity = "DEBUG"` にマッピングし、`level = "TRACE"` をメタデータとして保持する。
- これにより、Google Cloud Loggingのネイティブフィルタ（`severity >= DEFAULT`）で `DEBUG` と同様に集約され、Cloud Loggingの標準仕様に反することなく透過的に扱われる。
