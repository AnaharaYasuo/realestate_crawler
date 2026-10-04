# Slack通知最適化・テスト時外部送信遮断およびチャンネル不整合是正 内部設計書 (Issue #642)

## 1. 詳細関数・インタフェース仕様

### 1.1 `package/utils/slack.py`

#### 1.1.1 `verify_slack_credentials(token: str | None = None) -> tuple[bool, str]`
* **目的**: Slack API の `auth.test` エンドポイントを叩き、Bot トークンが正当にワークスペースに接続可能か検証する（メッセージ投稿なし）。
* **処理フロー**:
  1. `token = token or os.getenv("SLACK_BOT_TOKEN")` を取得。無ければ `(False, "SLACK_BOT_TOKEN not configured")` を返却。
  2. `https://slack.com/api/auth.test` へ `Authorization: Bearer <token>` ヘッダー付きで POST リクエストを送信（timeout: 5.0s）。
  3. ステータス 200 かつ `resp_json.get("ok") is True` の場合、`(True, f"Authenticated as {resp_json.get('user')} (team: {resp_json.get('team')})")` を返却。
  4. それ以外の場合は `(False, f"Slack auth.test failed: {resp_json.get('error')}")` を返却。

#### 1.1.2 `get_alert_channel(property_type: str) -> str`
* **目的**: 種別ごとのアラートチャンネルIDまたはチャンネル名を集中解決する。
* **対応マップ**:
  - `mansion`: `os.getenv("SLACK_ALERT_MANSION", "C0BJWUCTRNU")` (`#alerts-mansion`)
  - `kodate`: `os.getenv("SLACK_ALERT_KODATE", "C0BHZA5ASDT")` (`#alerts-kodate`)
  - `tochi`: `os.getenv("SLACK_ALERT_TOCHI", "C0BJ2JVGCLS")` (`#alerts-tochi`)
  - `apartment` / `invest_apartment`: `os.getenv("SLACK_ALERT_INVEST_APARTMENT", "C0BJ6B4R3E0")` (`#alerts-invest-apartment`)
  - `invest_kodate`: `os.getenv("SLACK_ALERT_INVEST_KODATE", "C0BJ0KSJEDC")` (`#alerts-invest-kodate`)
  - その他 / デフォルト: `os.getenv("SLACK_ALERT_PROPERTY_ALERT", os.getenv("SLACK_CHANNEL_ID", "property_alert"))`

### 1.2 `src/crawler/tests/conftest.py`

#### 1.2.1 `block_outbound_slack_notifications(monkeypatch_session)`
* **スコープ**: `session` または `autouse=True` fixture
* **処理**:
  1. `monkeypatch.setenv("SLACK_BOT_TOKEN", "mock-test-bot-token-blocked")`
  2. `monkeypatch.setenv("SLACK_APP_TOKEN", "mock-test-app-token-blocked")`
  3. 万が一 `send_slack_message` の直接テスト以外のテストコードが `send_slack_message` を実行した場合、実ネットワーク通信を行わずモックまたは警告ログとともに即座にダミー成功/安全終了するようガード。
  4. これにより、個別テストでのパッチ漏れが発生しても本番環境へのテストメッセージ流出を 100% 物理遮断する。

### 1.3 `src/crawler/scripts/debug_tools/check_slack_connection.py`
* 従来の `send_crawling_summary_alert` の呼び出しを `verify_slack_credentials()` の呼び出しに置換。
* テストメッセージの投稿を完全に削除。

### 1.4 `src/crawler/scripts/ops/run_all_crawlers.py`
* 790行目付近：
  ```python
  # 変更前:
  asyncio.run(send_slack_message(message=auto_heal_msg, channel="#dev-agent"))
  # 変更後:
  asyncio.run(send_dev_report(auto_heal_msg))
  ```

### 1.5 `src/crawler/scripts/maintenance/validate_data.py`
* 240行目付近：
  ```python
  from package.utils.slack import get_alert_channel
  alert_channel = get_alert_channel(key)
  ```

### 1.6 `src/crawler/scripts/ops/run_all_crawlers.py` (詳細処理 vs 未変更スキップ集計)
* **`get_count_for_job(company, ptype, start_dt) -> tuple[int, int] | tuple[None, None]`**:
  - `detail_count`: `inputDateTime >= start_dt` の件数（新規取得として詳細ページを処理して登録した物件）
  - `skipped_count`: `updateDateTime >= start_dt AND (inputDateTime < start_dt OR inputDateTime IS NULL)` の件数（一覧ページで未変更と検知され詳細ページをスキップし `updateDateTime` のみバッチ更新された既存物件、または価格改定・TTL期限切れで更新された既存物件）
  - `total_count = detail_count + skipped_count`
  - 返却値: `(detail_count, skipped_count)`
* **Slack メッセージ書式**:
  - ジョブ完了時:
    ```
    ✅ 【成功】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 詳細処理: {detail_cnt} 件 / 未変更スキップ: {skipped_cnt} 件 (計: {total_cnt} 件) | 処理時間: {duration_job_str}
    ```
  - サマリーレポート:
    ```
    • {comp} - {ptype}: 詳細処理 {detail_cnt} 件 / 未変更スキップ {skipped_cnt} 件 (計: {total_cnt} 件){timing_str}
    ```
