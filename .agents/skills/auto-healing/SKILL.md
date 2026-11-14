---
name: auto-healing
description: 直近のクローリング監視や全アラートSlackチャンネルで検出されたパースエラー・0件取得異常を、AIが自律的に調査・修正し、修正後に共通の /regression-test ワークフローを呼び出して復旧・修復（Self-Healing）するためのスキルです。
---

# 自律型AIパーサー自己修復 (Self-Healing) スキル

このスキルは、クローリング監視アラートや0件取得検出時（またはユーザーからの `/auto-heal` 指示時）にトリガーされ、人手を介さずに全自動でバグ修正および後修復検証を行う実行ガイドラインです。

## 実行原則（トークン節約＆効率化）
* **証拠起点調査原則 (Evidence-First Investigation) ＆ 保存生HTML最優先利用**:
  - 自己修復調査を行う際、**必ず直近の実行ログで保存された logs/runs/<日付>/error_pages/ または GCS 上のエラー生HTML（一覧0件時の zero_count_list.html や詳細パース失敗HTML）をオフラインで読み込み、DOM構造やエラーメッセージの事実確認を行うことを絶対義務**とする。現場の生HTMLを確認せずに外部サイトへの再リクエストを推測で行ってはならない。
* **発生頻度順（Top-50 First）優先修復 ＆ 実行契機の限定**:
  - 全体クローリング完了時（`run_all_crawlers.py` 末尾）または手動 `/auto-heal` 呼び出し時の**1回のみ**実行。物件ごとのクローリングループ内での常時・逐次実行は完全禁止。
  - 全方位の無差別探索を行わず、`Temp/auto_heal_instruction.json` または障害テレメトリから**発生件数の多いエラー上位（最大50件）**を抽出し、頻度順に1件ずつピンポイントで修復する。
* **ローカルへの生ログ読み込み完全禁止 (Direct-to-AI / No Local Log Ingestion)**:
  - ローカルマシン環境や Antigravity のコンテキストに生ログ（数十〜数百行）を読み込むことを完全禁止。
  - エラー集計・要約はコンテナ内メモリから Google Cloud Gemini (Flash) へダイレクトに送信し、AI が要約した数行の抜粋テキストのみを指示書・通知経由で受け取る。
* **Slackエラー＆低件数異常の自動インジェスト (Slack Telemetry Integration)**:
  - `auto_heal_parsers.py` が `SLACK_BOT_TOKEN` を用いてSlackのアラートチャンネル（`#alerts-*`、`#property_alert`、`#dev-agent`）から直近のエラーログ（0件取得警告、パース例外、大規模サイトの極小件数異常）を自動取得し、DBのデータ不整合スキャン結果と統合して指示書（`Temp/auto_heal_instruction.json`）を生成する。
  - 人手による個別チャンネル確認や無差別巡回を不要とし、Slack上の障害検知を唯一の集約指示書として直接AI自己修復の起点にする。
* **メインエージェント直接実行規約（サブエージェント使用禁止）**:
  - グローバルルールに従い、サブエージェント（`invoke_subagent` / `define_subagent`）はいかなる場合も起動しない。
  - メインエージェント自身が Gemini 要約済み指示書（`Temp/auto_heal_instruction.json` または GCS `auto_heal/latest_instruction.json`）および `ErrorPageReplayer` を用いて最小トークンで調査・修正・検証を完遂する。

## 実行ステップ

### 0. GitHub Issue ドリブン自動修復プロトコル（Scheduled Automation / Issue起点実行時）
1. **対象 Issue の高速判定**:
   - `python src/crawler/scripts/ops/sync_auto_heal_issues.py --list-actionable` を実行し、`count == 0` の場合は追加調査を行わず即座に完了報告して終了する（トークン消費最小化）。
2. **試行回数記録とサーキットブレーカー**:
   - 対象 Issue `#<N>` に着手する前に `python src/crawler/scripts/ops/sync_auto_heal_issues.py --record-attempt <N>` を実行する。試行上限（2回）を超過して `escalated: true`（`auto-heal:needs-human`）となった場合は作業を停止する。
3. **独立 Worktree での SDD × TDD × Parser 修正 ➔ `production` マージ＆本番デプロイ完遂**:
   - **【最重要・完了定義】自動修復のゴールは「`production` ブランチへのマージ完了および本番デプロイ（`Deploy Production`）の成功確認」である。PR作成時点や `master` マージ時点で作業を終了してはならない。**
   - 必ず `.worktrees/fix-<N>-auto-heal-<company>-<type>`（ブランチ `fix/<N>-auto-heal-<company>-<type>`）を作成して作業する。
   - 対象サイトの SDD 正本仕様書（`docs/2_crawlers/sites/` 等）の同期更新、回帰単体テスト（`src/crawler/tests/unit/`）の追加・更新、およびパーサー／セレクタの最小修正を行う。
   - 検証ゲート（`pytest`、`test_architecture_harness.py`、`check_local_sonar.py --diff`、ライブ疎通検証）がすべて合格したら、`python src/crawler/scripts/ops/sync_auto_heal_issues.py --mark-criteria-done <N>` で Issue の受入基準を `[x]` に更新する。
   - **Stage 1 (`master` マージ)**: PR（タイトル `[#<N>] fix(<company>): ...`、本文 `Closes #<N>`）を作成し、`check_pr_ci_status.py` で全CI合格を確認して `master` へマージする。
   - **Stage 2 (`production` マージ ＆ デプロイ完了確認)**: 自動生成（または手動作成）された `master` ➔ `production` リリースPR の CI 合格を確認して `production` へマージし、GitHub Actions `Deploy Production` ワークフローが `success` で完了（Cloud Run 本番反映 ＆ 異常物件再クロール起動）するところまで必ず見届けてから Worktree をクリーンアップする。
   - サイト側の大規模仕様変更・CAPTCHA遮断等で自動修正不能な場合は `python src/crawler/scripts/ops/sync_auto_heal_issues.py --escalate <N> --reason "<根本原因>"` を実行して人手対応へ引き継ぐ。

### 1. 指示書およびエラー集計からの修復対象特定（Top-50）
* まず `python src/crawler/scripts/debug_tools/auto_heal_parsers.py --pull-from-gcs` でクラウド最新の `Temp/auto_heal_instruction.json` を同期する（ローカルDB接続済みの場合は引数なしで直接再集計も可能）。指示書に記録された Gemini AI による要約（`ai_summary`）および発生頻度上位（最大50件）の修復対象を特定。
* 大規模ポータル（athome, homes等）で0件警告や極小件数が記録されている場合、一覧URL抽出セレクター、ページネーション、あるいはアクセス遮断を最優先で調査・修復。
* 同一サイト＆種別で大量（数十〜200件等）の失敗が発生している場合は、`python src/crawler/scripts/debug_tools/bulk_auto_heal_diagnose.py --site <site> --type <type>` を実行し、全失敗サンプルを圧縮して Gemini Flash へ1リクエスト投入することで、包括的修正マニフェスト（`Temp/auto_heal_bulk_fix_manifest.json`）を生成して一括原因究明を行う。
* ローカルへのログファイルの引き出し・読み込みは行わず、指示書の要約情報および対象URL・パーサーを直接確認。
* パーサー未整備エラー（`[PARSER_UNAVAILABLE]`）が検知された場合、新規パーサー開発対象（Backlog）として自律的に開発タスクを起票・実装する。
* 対象パーサー（`src/crawler/package/parser/`）、セレクター、正規表現、またはルートを上位エラーから順番に修正。

### 2. リグレッションテストの呼び出し
* 修正完了後、スキル/ワークフロー `/regression-test` を呼び出し、セキュリティ走査・動的二段階検証・処理時間アサーション・pytest全パスを確認すること。
* **モックHTMLファイル依存の完全排除**: ローカルの固定モックHTMLファイル（`tests/error_pages/` 等）によるテストは全廃とし、必ず最新アクティブ公開中の物件HTML（動的取得）またはライブ到達テストで検証すること。

### 3. 自己修復完了報告プロトコル（必須報告事項）
* 自己修復およびテスト検証の完了時には、必ず以下の3項目を構造化して明示・報告すること：
  1. **問題事象**: 発生していたエラー内容、影響を受けた対象サイト・物件種別・URL・エラー件数および根本原因。
  2. **修正内容**: 修正したファイル（パーサー、セレクター、正規表現、設定ファイル等）のパスおよび具体的な変更差分。
  3. **修正後の動作確認結果**: 実施したテスト（`pytest`、`task test-live`、動的取得検証など）のコマンドおよび全件成功（Pass）の客観的事実・証跡。

