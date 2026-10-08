# 要件定義書: ログ出力改善・TRACE/DEBUG新設およびノーレベル出力禁止要件 (Issue #783)

## 1. 背景と目的
現在、システム内で `INFO` レベルのログが過剰に出力されており（各物件・URL走査、セレクター解決、APIルーティング追跡、微小ステップ等）、本番運用および障害調査時において重要なシステムイベント（パイプライン進行、バッチ完了、エラー発生等）の可読性が著しく低下している。
また、レベルが付与されていない出力（`print` 関数等の直接標準出力）が一部残存しており、構造化ログ（Google Cloud Logging / JSON）のフォーマット整合性を損ねる要因となっている。

本要件では、以下のログ基盤改善を定義する：
1. レベルなしログ出力（`print` 文等の直接出力）の禁止および `logger`/`logging` 経由への一本化
2. 新たなログレベル `TRACE` (レベル値 5) の新設、および既存 `DEBUG` (レベル値 10) と連携した階層的ログ制御
3. 現在 `INFO` で出力されている大量の走査・パース・リクエスト追跡ログの `DEBUG` / `TRACE` への適正移行

## 2. 機能要件

### FR-LOG-001: ログレベルなし出力の完全禁止
- システム内の全コードにおいて、ログレベルが付与されない標準出力（`print()` 関数の直接使用など）を禁止する。
- すべての出力は `logger` (`structlog.BoundLogger` または `logging.Logger`) を経由し、必ず明確なログレベル（`TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`）を付与して出力すること。

### FR-LOG-002: TRACE (5) / DEBUG (10) ログレベルの新設・定義
- 標準の `logging` モジュールおよび `structlog` において、`TRACE` レベル（数値: 5）を新設・登録すること。
- `logger.trace(...)` および `logging.trace(...)` メソッドによる呼び出しをサポートすること。
- Google Cloud Logging（JSON形式）出力時、`TRACE` は `DEBUG` 相当（`severity: "DEBUG"`、詳細フィールドに `original_level: "TRACE"` 等）として安全に整形・マッピングされること。

### FR-LOG-003: ログレベル環境変数設定とフィルタリング
- 環境変数 `LOG_LEVEL` により、`TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` のいずれかを設定可能とすること（デフォルトは `INFO`）。
- `LOG_LEVEL=INFO` 時には `TRACE` および `DEBUG` は一切出力されず、`LOG_LEVEL=DEBUG` 時には `DEBUG` 以上が出力され `TRACE` は抑制され、`LOG_LEVEL=TRACE` 時には全ログが出力されること。

### FR-LOG-004: 既存 INFO ログの TRACE / DEBUG 適正化
- 以下の高頻度・微細ログを `INFO` から `DEBUG` または `TRACE` へ移行すること：
  - **`DEBUG` 移行対象**:
    - 単一URLへの遷移、ルーティング開始/終了（例: `[Keikyu] Match detail link`, `Start mitsuiMansionStart`, `Success ...` 等）
    - 単一物件の詳細パース開始/終了、掲載終了判定ログ（`MSG_LISTING_ENDED_PREFIX` 等）
    - ミドルウェアでの個別APIリクエスト/レスポンスログ（`[API Request]`, `[API Response]`）
    - キャッシュ操作・セレクター読み込み（`Loaded selectors for ...`）
  - **`TRACE` 移行対象**:
    - XPath / CSS セレクターの取得・評価文字列（例: `[mansion] property_list_xpath: ...`, `getPropertyListNextPageUrl` 等）
    - 個別HTML要素・リンクの探索・正規化詳細
- **`INFO` に維持する対象**:
  - クローラー全体の開始・完了サマリー
  - 取得件数・保存件数・エラー件数の集計結果
  - バッチ・MLパイプラインのフェーズ移行
  - Slack通知・アラート発報イベント
