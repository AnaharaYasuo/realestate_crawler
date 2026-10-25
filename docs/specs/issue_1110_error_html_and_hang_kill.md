# 仕様ドキュメント: 全エラー時生HTML完全保存・証拠起点調査・ハング即殺 (Issue #1110)

## 1. 概要
クローラーのパイプライン実行における障害発生時、原因追究のための生HTML証拠（エビデンス）の保存漏れを根絶し、4時間上限に達する前の迅速なハング強制終了（即時SIGKILL）および、調査時に保存生HTMLを活用する運用原則を確立する。

---

## 2. 要件定義

### 2.1 エラー時生HTML完全保存（6大エラー事象の網羅）
1. **一覧0件取得（ZeroCountFailure）**:
   - 一覧ページ取得後に抽出できた物件リンクが0件の場合、対象の一覧ページ生HTMLおよびメタデータを即座に保存する。
2. **アクセス遮断・ボット検知（Challenge / Block / Captcha）**:
   - HTTP 403, 429、または各種CAPTCHA/Cloudflare等のチャレンジ画面返却時、そのレスポンスHTMLを保存する。
3. **サーバー障害（HTTP 5xx）**:
   - 相手方サーバーが返却したエラー画面やメンテ画面のHTMLを保存する。
4. **詳細バリデーション失敗（Strict Extraction Failure）**:
   - 必須項目（価格、住所、物件名等）の抽出失敗時に詳細ページ生HTMLを保存する。
5. **掲載終了・404（Listing Ended / Disappeared）**:
   - 物件削除・非公開画面の生HTMLを保存する。
6. **ハング・タイムアウト直前**:
   - タイムアウトや無音検知で強制終了される際、可能な限り最後のレスポンス・DOMスナップショットを記録する。

### 2.2 ハング即時強制終了（Hang Instant Kill）
- `HANG_THRESHOLD_SEC`:
  - 環境変数が未設定（または0）の場合でも、無期限放置（4時間タイムアウト到達）を防ぐため、**デフォルト値を 300秒（5分）** に設定する。
  - 5分間進捗ファイル（mtime）およびDB件数の更新がない無音状態を検知した時点で、即座に対象プロセスグループへ SIGKILL を発行し、Slackおよびメトリクスへ報告する。

### 2.3 証拠起点調査原則（Evidence-First Investigation）の明文化
- `.agents/skills/auto-healing/SKILL.md` および `.agents/skills/troubleshooting-and-logging/SKILL.md` に「調査時には必ず保存された `error_pages` をファーストソースとして読み込み、推測や無駄な外部再リクエストを行わない」原則を規定する。

---

## 3. 内部設計

### 3.1 `package/utils/crawler_watchdog.py`
- `_parse_hang_threshold()` のデフォルト値を `300.0`（5分）に変更。
- 無効化したい場合は環境変数で明示的に `-1` や `0` を指定した場合のみとする。

### 3.2 `package/parser/baseParser.py` & `package/api/api.py`
- 一覧パース時に結果が0件であった場合、直ちに `save_error_html(url, content, reason="Zero count on list page")` を呼び出す。
- `FailureReporter.record_job_failure` 側でも、0件やエラー終了時に渡された `raw_html` を確実にストレージへ保存する。

### 3.3 スキル・運用ルールの更新
- `troubleshooting-and-logging` および `auto-healing` に Evidence-First 原則を追加。
