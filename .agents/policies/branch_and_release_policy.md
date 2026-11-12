# ブランチ運用およびリリース完了ポリシー (Branch and Release Policy)

## 1. 目的と存在理由 (Why)
並行作業時のコンフリクト根絶、変更の完全なトレーサビリティ確保、および本番デプロイ完了までの確実な遂行を目的とします。

---

## 2. コア規範 (Rules & Boundaries)

### 2.1. 常時 git worktree 運用原則 (Always Worktree Principle)
- メイン作業ツリー（リポジトリルート）で直接ブランチを切り替えて作業してはならない。
- 必ず `git worktree add .worktrees/<branch-name> -b <branch-name>` で独立したワークツリーを作成して作業すること。

### 2.2. 作業着手前の最新同期義務 (Pre-Flight Master Sync)
- 作業開始前に必ず `git checkout master && git pull origin master` および `cmd /c codegraph sync` を完了した上で、作業ブランチを作成すること。

### 2.3. 不可逆開発順序（Issue-Driven × Spec-Driven × Test-Driven）＆ Issue未紐付けPR完全禁止原則
- **不可逆ライフサイクルの厳守（順序逆転・省略の絶対禁止）**:
  1. **Issue先行起票**: コードや仕様書に触れる前に必ず GitHub Issue を未完了受入基準（`- [ ]`）付きで起票し、Issue番号入りの `.worktrees/<type>-<issue_num>-<slug>` を作成する（起票時点で `- [x]` を先付けしてはならない）。
  2. **7大ドメイン正本ドキュメント先行更新 (SDD)**: 実装前に必ず `docs/1_architecture/` 〜 `docs/7_operations_and_improvement/` の該当正本仕様書を更新する（`.agents/policies/` のみの更新で `docs/` 正本更新を代替してはならない）。
  3. **テスト先行作成・Red確認 (TDD)**: 実装前に単体テストを作成し、`pytest` で **Red（失敗）** を客観的に確認してから最小コードを実装して **Green（合格）** にする。
  4. **ハーネス検証 ＆ 受入基準完了化**: `test_architecture_harness.py` 合格を確認した後に Issue の `- [ ]` を `- [x]` に更新し、タイトル先頭に `[#<Issue番号>]`・本文に `Closes #<Issue番号>` を付与して PR を作成する。
- **Step 1 (作業ブランチ ➔ `master`)**:
  - **IssueなしのPR作成・プッシュ・マージは全面禁止**とし、以下の3層ゲートで機械的に強制する（Issue #1395）：
    1. **ローカル PreToolUse ゲート (`.agents/scripts/hook_guard.py`)**: `production` 向けリリースPRを除くすべての `gh pr create` において、タイトル `[#<Issue番号>]` および本文 `Closes #<Issue番号>`（または `Fixes` / `Resolves`）の明示記載がないコマンド実行を即座に Deny する。また Issue 番号を含まない作業ブランチの `git push`（削除操作を除く）も Deny する。
    2. **GitHub Actions CI ゲート (`.github/workflows/issue-gate.yml` + Branch Protection `enforce_admins: true`)**: PR本文の `Closes/Fixes/Resolves #<Issue番号>` 記載、対象 Issue が実在かつ **`open` 状態**であること、および受入基準チェックボックス（`- [x]`）が全件完了していることを検証する。Issue未紐付けまたはクローズ済みIssue指定のPRは自動的に `closed` へ遷移させ、マージをブロックする。
    3. **アーキテクチャ・ハーネス検証 (`test_architecture_harness.py`)**: 上記2層のルール定義が削除・弱体化されていないことを常時自動テストする。
  - CI 全件合格後に `master` へマージ。
- **Step 2 (`master` ➔ `production`)**:
  - `production` への PR は `master` からのみ許可（`production-gate.yml`）。
  - マージ完了により本番デプロイパイプライン（`deploy-production.yml`）が起動。

### 2.4. タスク完了の定義原則 (Production Merge Definition of Done)
- **プロダクション（`production` ブランチ）へのマージ完了をもって初めてタスク完了とする。**
- `master` へのマージ完了時点で作業を終了とみなしてはならない。
- 関連スキル: [git-push-workflow](../skills/git-push-workflow/SKILL.md)
