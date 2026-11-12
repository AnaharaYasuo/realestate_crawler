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
   - `.agents/scripts/hook_guard.py`（Antigravity PreToolUse ゲート / Issue #1395）: `production` 向けリリースPRを除くすべての `gh pr create` に対し、タイトル `[#<issue_num>]` および本文 `Closes/Fixes/Resolves #<issue_num>` が欠落しているコマンド実行を水際で即時遮断（Deny）し、Issue番号を含まない作業ブランチの `git push` も遮断する。
   - `.github/workflows/issue-gate.yml`（GitHub CI 必須ゲート `enforce_admins: true` / Issue #1395）: 管理者を含め誰一人として Issue-Driven・Spec-Driven (SDD)・Test-Driven (TDD) を逸脱できないよう、以下の4大ゲートを CI 上で機械的に強制する：
     1. **Issue-Driven 厳格検査**: PR本文の `Closes/Fixes/Resolves #<issue_num>` 明示記載、PRタイトル先頭 `^\[#<issue_num>\]\s+` および作業ブランチ名 `<issue_num>` との3点完全一致、対象 Issue が実在かつ `open` 状態であること、ならびに **Issue作成日時 `<=` PR作成日時**（PR提出後の事後Issue起票禁止）を検証する。Issue未紐付け・PR番号誤指定・クローズ済みIssue流用PRは即時自動クローズ（`state: 'closed'`）する。
     2. **受入基準 ＆ PRチェックリスト完了検査**: Issue本文の受入基準チェックボックス `- [x]` が1件以上定義され未完了 `- [ ]` が0件であること、かつ PR本文内（コードブロック外）にも未完了 `- [ ]` が残存していないことを検証する。
     3. **Spec-Driven (SDD) 7大ドメイン正本更新必須ゲート**: PR差分（`pulls.listFiles`）に非テスト実装・インフラ・CIワークフロー・エージェント設定（`src/**`［`src/crawler/tests/**` 除く］、`terraform/**`、`.github/workflows/**`、`.agents/**`）の変更が含まれる場合、必ず7大ドメイン正本仕様書（`docs/1_...`〜`docs/7_.../*.md`）の更新が同一PR内に含まれることを必須とし、未更新時はマージを遮断する。
     4. **Test-Driven (TDD) テストコード変更必須ゲート**: PR差分に実行可能コードまたはワークフロー定義（`src/**/*.py`［`src/crawler/tests/**` 除く］、`.agents/scripts/**/*.py`、`.github/workflows/*.yml|*.yaml`）の変更が含まれる場合、必ず `src/crawler/tests/**/*.py` 配下のテストコード追加・更新が同一PR内に含まれることを必須とし、未追加・未更新時はマージを遮断する。
   - `.agents/AGENTS.md` & `git-push-workflow`: PR提出・プッシュ前にローカル100%合格を客観的ログで確認することを義務化。

## 4. 非機能要件 (Non-Functional Requirements)
- **実行速度**: 高速差分モード（`--diff`）は差分対象のみ検査し、最小限のオーバーヘッドで完了すること。
- **可読性**: 検証結果をコンソールおよびサマリーテーブル形式で一目で把握可能とすること。
