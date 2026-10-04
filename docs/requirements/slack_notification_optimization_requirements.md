# Slack通知最適化・テスト時外部送信遮断およびチャンネル不整合是正 要件定義書 (Issue #642)

## 1. 概要・ユーザーストーリー
* **ユーザーとして**: 不動産クローラー運用の開発者・保守管理者として
* **要求**: 
  1. pytest 実行時や開発中にテスト用のアラート文面が本番 Slack チャンネル（`#property_alert` 等）へ誤送信される事故を根絶したい。
  2. バッチ起動ごとの事前接続チェック（`check_slack_connection.py`）が無駄なメッセージ投稿でチャンネルを汚すのを防止したい。
  3. 各送信処理の送信先チャンネル（`run_all_crawlers.py`, `validate_data.py`, `run_pipeline.py`）を実態・環境変数定義と完全合致させたい。
* **価値**: 管理者・開発者チャンネルのノイズと誤報をゼロにし、テスト時の外部誤爆事故を物理的に遮断してシステム通知の信頼性を向上させる。

## 2. 背景と課題
1. **テスト時の本番 Slack 誤送信**:
   - `conftest.py` に Slack トークン無効化や送信スタブのセーフティネットが存在せず、ユニットテスト内でモック漏れがあった場合に実 API へリクエストが着弾する事故が発生した（2026-10-04 08:34 JST のテストアラート誤爆）。
2. **事前接続確認による不要メッセージ投下**:
   - `check_slack_connection.py` が「🔄 【接続テスト】 パイプライン事前接続チェックを実行中...」という実メッセージを毎日夜間に `#property_alert` へ投稿し、運用上のノイズとなっている。
3. **送信先チャンネル指定の不整合**:
   - `run_all_crawlers.py` の自動修復トリガーが生文字列 `channel="#dev-agent"` で送信され、環境変数 `SLACK_DEV_CHANNEL`（ID解決）が適用されていない。
   - `validate_data.py` の個別アラートチャンネルIDがコード内にハードコードされている。
   - `run_pipeline.py` の緊急アラートが `#property_alert` と `#dev-agent` に同一文面で無条件二重送信されている。

## 3. 機能要件 (Functional Requirements)
* **FR-001: テスト環境下の Slack 送信完全遮断 (Test Isolation Guard)**
  - pytest 実行時（`conftest.py`）において、環境変数 `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` を安全なダミー値に隔離すること。
  - さらに `send_slack_message` 関数に対してテスト時のデフォルトセーフティネット（実送信防止フラグまたは警告スキップ）を設けること。
* **FR-002: 事前接続チェックのサイレント化 (Silent Slack Health Check)**
  - `check_slack_connection.py` において、実メッセージ投稿ではなく Slack API の `auth.test`（またはトークン・権限確認 API）を呼び出して疎通確認を行い、チャンネルにメッセージを残さないこと。
* **FR-003: 開発・修復チャンネル指定の一元化 (Unified Dev Channel Routing)**
  - `run_all_crawlers.py` の自律修復トリガー送信先を `os.getenv("SLACK_DEV_CHANNEL", "C0BKBHWD26T")` を使用する `send_dev_report` 経由に統一すること。
* **FR-004: データ監視アラートチャンネル設定の集中化 (Alert Channels Centralization)**
  - `validate_data.py` のアラート送信先を `package/utils/slack.py` の集中定義（`KNOWN_ALERT_CHANNEL_IDS` および環境変数）と連携させ、ハードコードを排除すること。
* **FR-005: パイプライン緊急通知の責務分離 (Pipeline Alert Role Separation)**
  - `run_pipeline.py` のタイムアウト・緊急停止通知において、運用アラートは `#property_alert` に集約し、AIへの自動修復依頼（`[AGY-REQ:AUTO-HEAL]`）を伴う場合のみ `#dev-agent` へ送るよう役割を明確化すること。
* **FR-006: クローリング処理件数の内訳通知 (詳細処理件数 vs 未変更スキップ件数)**
  - `run_all_crawlers.py` のジョブ完了通知および24時間サマリーレポートにおいて、サイト・物件種別ごとの処理件数を「詳細ページの処理をした件数 (詳細処理)」と「一覧で未変更を検知して詳細ページの処理をしなかった件数 (未変更スキップ)」の内訳に分割して通知すること。
  - ジョブ完了時メッセージ例: `✅ 【成功】 {company} - {ptype} (Job {idx}/{total}) | 詳細処理: {fetched} 件 / 未変更スキップ: {skipped} 件 (計: {total} 件) | 処理時間: {duration}`
  - サマリーレポート例: `• {comp} - {ptype}: 詳細処理 {fetched} 件 / 未変更スキップ {skipped} 件 (計: {cnt} 件)`

## 4. 非機能要件 (Non-Functional Requirements)
* **NFR-001: 既存のお宝物件通知（`goodproperty-*`）の完全保全**
  - エンドユーザー向けのお宝物件推薦配信のチャンネル振り分けやフォーマットに一切悪影響を与えないこと。
* **NFR-002: テストの可搬性と高速性**
  - 単体テスト実行時にネットワーク接続を必要とせず、高速かつ決定論的にパスすること。

## 5. アクセプタンスクライテリア (受入基準)
* [ ] 【基準1】pytest 実行環境下において、モック漏れのテストコードであっても実 Slack API への HTTP リクエストが 100% 遮断されること。
* [ ] 【基準2】`check_slack_connection.py` がチャンネルへメッセージを投稿することなく、Bot のトークン有効性・権限を検証して正常終了すること。
* [ ] 【基準3】`run_all_crawlers.py` の自動修復トリガーが環境変数 `SLACK_DEV_CHANNEL` または `send_dev_report` を経由して送信されること。
* [ ] 【基準4】`validate_data.py` の個別アラートチャンネル指定がハードコードではなく集中定義と環境変数を参照すること。
* [ ] 【基準5】`run_all_crawlers.py` のジョブ完了時通知およびサマリー通知において、サイト・物件種別ごとに「詳細処理件数」と「未変更スキップ件数」の内訳が明示されること。
* [ ] 【基準6】すべての単体テストおよびリグレッションテストが正常に通過すること。
