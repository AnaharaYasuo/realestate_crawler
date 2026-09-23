# 内部設計書: Prodマージ高速化・CIトリガー最適化・Dependabot集約の一貫改善 (Issue #376)

## 1. 内部ロジック詳細設計

### 1.1 `auto-release-pr.yml` のスクリプト実装設計

* **実行環境**: `ubuntu-latest`
* **権限 (permissions)**:
  - `contents: write` (PR作成、ブランチ読み取り)
  - `pull-requests: write` (PR作成、Auto-merge設定、コメント)
  - `issues: read` (Issueタイトルの解決)
* **ステップ構成**:
  1. `actions/checkout@v7.0.1` (fetch-depth: 0)
  2. `check-and-create-pr`:
     - GitHub CLI (`gh`) または GitHub Script を利用。
     - `gh pr list --base production --head master --state open --json number` を実行。
     - 既存PRが存在しない場合:
       - `git log origin/production..HEAD --oneline` で差分コミット一覧を取得。
       - コミットログから `(#\d+)` または `[#\d+]` を抽出し、`Closes #...` のリストを生成。
       - タイトルを `release: <latest_master_subject>` として `gh pr create`。
       - `gh pr merge <PR_NUMBER> --auto --merge` を実行（auto-merge有効化に失敗してもパイプライン全体は落とさず警告扱いとする）。

### 1.2 `review-gate.yml` の Production Fast-Pass ロジック設計

* **変更箇所**: `verify-conversations-resolved` ジョブのスクリプト初期部分。
* **ロジック**:
  ```javascript
  const targetBranch = pr.base && pr.base.ref;
  if (targetBranch === 'production') {
    core.info('🚀 Production PR detected: Bypassing conversation and checkbox gates (already validated on master).');
    await github.rest.repos.createCommitStatus({
      owner,
      repo,
      sha: headSha,
      state: 'success',
      context: 'review-gate',
      description: 'Production release PR: review gate bypassed (verified on master)'
    });
    return;
  }
  ```
* **効果**: API呼び出し回数を1回に抑え、未解決コメントやチェックボックスによる誤判定を完全抑止。

### 1.3 `dependabot.yml` のグループ構成設計

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/src/crawler"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 3
    groups:
      python-dependencies:
        patterns:
          - "*"

  - package-ecosystem: "terraform"
    directory: "/terraform"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 2
    groups:
      terraform-dependencies:
        patterns:
          - "*"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 2
    groups:
      actions-dependencies:
        patterns:
          - "*"

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 2
    groups:
      docker-dependencies:
        patterns:
          - "*"
```

### 1.4 `.coderabbit.yaml` の設定変更

`reviews.auto_review.base_branches`:
```yaml
    base_branches:
      - "master"
```
（`production` を完全に削除）

### 1.5 `.github/workflows/test.yml` のトリガー変更

```yaml
on:
  push:
    branches: [ main, master, production ]
  pull_request:
    branches: [ main, master ]
```
（`pull_request.branches` から `production` を削除）

## 2. テスト設計 (TDD)

テストファイル: `src/crawler/tests/test_prod_merge_ci_speedup.py`

* **Test 1 (`test_coderabbit_excludes_production_branch`)**:
  - `.coderabbit.yaml` を読み込み、`base_branches` に `production` が含まれず `master` のみであることを検証。
* **Test 2 (`test_test_workflow_excludes_production_pr`)**:
  - `.github/workflows/test.yml` を読み込み、`pull_request.branches` に `production` が含まれていないこと、`push.branches` には `production` が残されていることを検証。
* **Test 3 (`test_review_gate_bypasses_production_pr`)**:
  - `.github/workflows/review-gate.yml` を読み込み、`targetBranch === 'production'` 時にステータスを即座に `success` で登録してバイパスするコードが含まれていることを検証。
* **Test 4 (`test_dependabot_groups_configured`)**:
  - `.github/dependabot.yml` を読み込み、各エコシステムに `groups` が正しく定義され、`open-pull-requests-limit` が制限されていることを検証。
* **Test 5 (`test_auto_release_pr_workflow_exists_and_valid`)**:
  - `.github/workflows/auto-release-pr.yml` が存在し、`push: branches: [master]` でトリガーされ、`gh pr create` および `gh pr merge --auto` の記述を含むことを検証。
