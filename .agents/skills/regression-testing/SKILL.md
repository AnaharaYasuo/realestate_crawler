---
name: regression-testing
description: あらゆるコード変更（機能追加・バグ修正・リファクタリング）の後、Snyk/Sonar全コード走査、動的アクティブ生HTMLによる二段階検証（3件->20件）、パース時間アサーション、およびpytest全件合格を一貫して実行するための共通品質保証スキルです。
---

# 共通リグレッションテスト ＆ セキュリティ品質検証スキル

このスキルは、あらゆるコード変更（不具合修正、機能追加、リファクタリング、設定変更等）を行った後に**必ず呼び出される共通リグレッションテスト・品質検証ガイドライン**です。

## 実行ステップ

### 1. Snyk & SonarQube 全コード走査
* リポジトリ全域のセキュリティ脆弱性・型エラー・静的解析警告（Snyk / SonarQube / IDE Problems）を全件検出・修正し、エラーをゼロにする。

### 2. オフライン CRAWL_JOBS カタログ同期ゲート
* `task test-catalog`（`test_crawl_job_catalog_sync.py`）を実行し、本番ジョブ定義 `CRAWL_JOBS` の全件が Start API・シードURL・ディスパッチマップに解決できることを確認する。
* 部分ハードコードの別マトリクスは禁止。未解決ジョブがあれば FAIL。

### 3. 動的生HTML ＆ 全ジョブクローリング保証 (固定モック依存の完全排除)
* `task test-live`（`run_live_crawl_guarantee.py` → `test_live_crawl_guarantee.py`）を実行し、**全 CRAWL_JOBS** について本番パーサー経路で詳細URL抽出＋必須フィールドパース＋ページング＋物件種別判定を検証する。
* **並列プラン（ローカル vs CI）**: `package.utils.live_parallel` が環境判定する。ローカルは静的群 `-n 4`＋Playwright `mizuho → (sekisui ∥ athome)`、GitHub Actions は静的群 `-n auto`＋同スケジュール。`CRAWL_LIVE_PARALLEL_MODE` / `task test-live MODE=ci` で上書き可。PR integration は `-m "not live"`。
* **修正確認時の部分実行**: `task test-live SITES=sumifu,odakyu` または `COMPANY=sumifu TYPE=mansion` で対象サイト/ジョブのみ検証してよい（環境変数 `CRAWL_GUARANTEE_SITES` / `_COMPANY` / `_TYPE`）。PR 完了・受入前は必ずフィルタ無しの全件 `task test-live` を通す。
* 詳細URL 0件は Zero-Count Failure として FAIL（本番クローリング失敗をテストで再現）。
* Phase 1（`CRAWL_SMOKE_SAMPLE_SIZE=3`）➔ Phase 2（最大20件）へ拡張可能。
* **ページング**: `parseNextPage` 成功（次ページ取得または exhausted）を必須。
* **物件種別**: `PropertyTypeDetector` とジョブ想定種別の一致を必須。

### 4. 純処理時間アサーション (パフォーマンスアサーション)
* ネットワーク通信待ち時間を除外した「純粋なDOM/パース処理時間」を計測し、以下の閾値を超過した場合はパフォーマンス劣化バグとしてFAIL判定する：
  * **静的HTMLパーサー（三井・住友・東急・野村・ミサワ等）**: 1,000ms（1.0秒）以内/件
  * **動的ブラウザパーサー（Playwright使用サイト: Athome等）**: 5,000ms（5.0秒）以内/件

### 5. pytest 全テスト（単体＋ライブ到達・全フィールド統合テスト）実行
* `docker compose exec -T app pytest src/crawler/tests/` を実行し、既存単体テストおよび動的ライブ到達・クローリング保証統合テストを含めて全件 PASSED (100% SUCCESS) であることを裏付ける。


### 6. Slack へのテスト結果自動通知投稿
* テスト完了後、テスト実行結果のサマリー（通過数、スキップ数、検出・修正された課題、および100% SUCCESS判定）を Slack のアラート/開発チャンネルへ自動投稿する。
* 投稿完了後は自ら Slack API を使用して投稿内容・スレッド表示・フォーマットを自己検証・裏付けること。
