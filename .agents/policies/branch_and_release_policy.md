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

### 2.3. 二段階マージゲートウェイ (Two-Stage Release Flow)
- **Step 1 (作業ブランチ ➔ `master`)**:
  - GitHub Issue の事前起票および紐付けが必須（`.githooks/pre-push` および `issue-gate.yml` で検証）。
  - CI 合格後に `master` へマージ。
- **Step 2 (`master` ➔ `production`)**:
  - `production` への PR は `master` からのみ許可（`production-gate.yml`）。
  - マージ完了により本番デプロイパイプライン（`deploy-production.yml`）が起動。

### 2.4. タスク完了の定義原則 (Production Merge Definition of Done)
- **プロダクション（`production` ブランチ）へのマージ完了をもって初めてタスク完了とする。**
- `master` へのマージ完了時点で作業を終了とみなしてはならない。
- 関連スキル: [git-push-workflow](../skills/git-push-workflow/SKILL.md)
