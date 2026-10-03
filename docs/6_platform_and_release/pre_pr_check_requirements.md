# PR事前全検証機構（Pre-PR Check）要件定義書

## 1. 概要・目的
GitHub PR提出後に実行される各種CIゲート（Issue PR Gate, Parser Tests, SonarCloud, PR Mutation Testing, Security Scan, Review Conversation Gate）でのチェック落ち・手戻りを根本から排除するため、PR提出前にローカルで全CIチェック相当の検証を一括実行し、全項目合格（100% PASS）しない限りPR提出を物理的・運用的に遮断・防止する機構を定義する。

## 2. 背景と課題
- **課題1: CIチェック落ちの多発**
  - 受入基準チェックボックスの未チェック (`- [ ]`) のままPR提出して `issue-gate.yml` で即時FAIL。
  - ローカル未実行の単体テストやPRミューテーションテスト（キル率80%未満）がCI上で失敗。
  - SonarCloud（S3776 複雑度, S8786 ReDoS）や Linter（Ruff）の警告が後から発覚。
- **課題2: 事前検証の断片化と厳守の欠如**
  - `check_issue_criteria.py` や `check_local_sonar.py` が個別存在しているが、一括実行する仕組みがなく実行が漏れる。
  - `git push` や `gh pr create` を直接叩いてしまい、事前検証をバイパスできてしまう。

## 3. 機能要件 (Functional Requirements)
1. **一括事前検証エンジン (`pre_pr_check.py`)**
   - **REQ-1 (Git & ブランチ検証)**: `master`/`production` 直接作業の遮断、ブランチ命名規則検証、危険な一時ファイル・機密情報の混入検査。
   - **REQ-2 (Issue & 受入基準検証)**: Issue実在確認および本文の全受入基準チェックボックス（`- [ ]`）がすべて完了（`- [x]`）していることの確認。
   - **REQ-3 (Linter & 静的解析 - SonarCloud必須検証)**: Ruff、SonarCloud（S3776 <= 15, S8786 ReDoS防止）、Python AST構文検査の実行。違反が1件でもある場合は即座にプッシュおよびPRを拒否。
   - **REQ-4 (CodeRabbit CLI レビュー必須検証)**: `coderabbit` CLI（`coderabbit review --agent`）を実行し、ローカル差分に対するAIレビューの実施可能性（認証・稼働）および重大な未解決指摘・エラーの有無を検証。未認証・実行エラー時はプッシュを遮断。
   - **REQ-5 (テストスイート実行)**: 単体テスト（`pytest -n auto src/crawler/tests/unit/`）および変更に応じた関連テストの自動実行。
   - **REQ-6 (PR Mutation Testing)**: `run_mutation_testing.py --pr-mode --threshold=80` の実行と合格判定。
   - **REQ-7 (セキュリティスキャン)**: Semgrep SAST（Python）、Checkov（Terraform変更時）の検証。
   - **REQ-8 (PRメタデータ事前検査)**: PRタイトルフォーマット（`[#<issue_num>] ...`）、本文の `Closes #<issue_num>`、およびPR本文に未完了チェックボックス（`- [ ]`）が存在しないことの事前検証。
2. **実行モード要件**
   - `--full`: 全8ステージ完全実行（PR作成時の必須ゲート）。
   - `--diff`: 変更ファイル対象の高速検証（コミット・プッシュ時向け。Stage 1-4 を必須実行）。
   - `--fix`: Linter自動修正オプション。
3. **厳守・遮断ガードレール要件**
   - `Taskfile.yml`: `task pr-check`（フル実行）、`task pr-check-fast`（差分実行）、`task coderabbit`、`task sonar-check`、`task pr-create`（全件合格時のみPR作成実行）。
   - `.githooks/pre-push`: Issue受入基準、SonarCloud静的解析、CodeRabbit CLIレビューを統合し、不備がある場合はリモートプッシュを水際でブロック。
   - `.agents/AGENTS.md` & `git-push-workflow`: PR提出・プッシュ前にローカル100%合格を客観的ログで確認することを義務化。

## 4. 非機能要件 (Non-Functional Requirements)
- **実行速度**: 高速差分モード（`--diff`）は差分対象のみ検査し、最小限のオーバーヘッドで完了すること。
- **可読性**: 検証結果をコンソールおよびサマリーテーブル形式で一目で把握可能とすること。
