# PR事前全検証機構（Pre-PR Check）内部設計仕様書

## 1. モジュール配置
- 検証本体スクリプト: `src/crawler/scripts/ops/pre_pr_check.py`
- CI ガバナンス4大ゲート判定エンジン: `src/crawler/package/utils/ci_governance_gate.py`
- 単体テスト: `src/crawler/tests/unit/test_pre_pr_check.py`, `src/crawler/tests/unit/test_ci_governance_gate.py`, `src/crawler/tests/unit/test_issue_1395_strict_issue_pr_gate.py`
- Pre-Push Gitフック: `.githooks/pre-push`
- タスク定義: `Taskfile.yml`

## 2. クラスおよび関数構成

### 2.1 データ構造
```python
@dataclass
class StageResult:
    stage_id: int
    name: str
    passed: bool
    details: str
    warnings: List[str]
    errors: List[str]
    duration_sec: float
```

### 2.2 検証ステージ詳細仕様

#### Stage 1: `check_git_and_branch()`
- カレントブランチ名取得 (`git rev-parse --abbrev-ref HEAD`)
- 保護ブランチ (`master`, `production`, `main`) への直接作業を検知
- ブランチ命名規則判定 (`feature/<issue_num>-...`, `fix/<issue_num>-...`)
- `git status --porcelain` でステージングされた不要ファイル (`Temp/`, `*.log`, `.env`) を検出

#### Stage 2: `check_issue_criteria()`
- `src.crawler.scripts.debug_tools.check_issue_criteria` の `fetch_issue_data` および `validate_issue_acceptance_criteria` を直接インポートまたはサブプロセスで呼び出し
- Issue の受入基準チェックボックス数 > 0 かつ 未完了チェックボックス数 == 0 をアサート

#### Stage 3: `check_linter_and_sonar()`
- 変更ファイル特定 (`git diff --name-only origin/master...HEAD` 等)
- `ruff check <files>` を実行 (インストール済みの場合は直接、または Docker 経由)
- `check_local_sonar.scan_file` を用いて、S3776 (Cognitive Complexity <= 15) および S8786 (ReDoS Regex Risk) を高速検証。違反が1件でもある場合はプッシュ・PRを遮断。

#### Stage 4: `check_coderabbit()`
- `coderabbit --version` でCLI導入状況を確認。
- `coderabbit review --base origin/master --agent`（または差分対象）を実行。
- CLI未インストール、未認証、実行失敗、または未解決の指摘（findings > 0）が存在する場合にエラーとし、プッシュ・PR作成を中断。
- 環境都合（CI環境やコンテナ外特定状況等）でスキップが必要な場合は `--skip-coderabbit` により明示指定可能とする。

#### Stage 5: `run_pytest_suite()`
- 変更差分に基づき、テスト対象を特定
- `pytest -n auto src/crawler/tests/unit/` を実行
- テスト失敗件数 == 0 をアサート

#### Stage 6: `run_mutation_testing()`
- `src.crawler.scripts.run_mutation_testing` の PR モード (`--pr-mode --threshold=80`) を実行
- キル率 (Mutation Score) >= 80% をアサート

#### Stage 7: `run_security_scan()`
- Python ファイル変更時: Semgrep スキャン
- Terraform ファイル変更時: Checkov スキャン

#### Stage 8: `validate_pr_metadata()`
- PR タイトル形式 (`[#<issue_num>] ...`)
- PR 本文の `Closes #<issue_num>` 存在確認
- PR 本文中の `- [ ]` 残存検知（GitHub Actions Review Gate と同様の正規表現ロジック）

### 2.3 `.githooks/pre-push` のコンテナ実行時 git メタデータ受け渡し（Issue #530）
- リポジトリ内 worktree（`.worktrees/<branch>`）の `.git` ファイルはホストの絶対パスを指すため、コンテナ内ではそのままでは解決できない。
- リポジトリ内 worktree 分岐では、`git rev-parse --absolute-git-dir` をメインリポジトリルートからの相対パスに変換し、`docker compose exec -e GIT_DIR=/app/<相対パス> -e GIT_WORK_TREE=/app/.worktrees/<branch>` として `pre_pr_check.py --diff` に渡す。

### 2.4 3層 Issue-Driven × Spec-Driven (SDD) × Test-Driven (TDD) 厳格遮断ゲート仕様（Issue #1395）
1. **Layer 1: PreToolUse エージェントフック (`.agents/scripts/hook_guard.py`)**
   - `_check_issue_pr_and_push_guard(cmd)` にて、`--base production`（リリースPR）以外の `gh pr create` 実行時に `\[#\d+\]`（タイトル先頭タグ）および `(?:Closes|Fixes|Resolves)\s+#\d+`（本文クローズ宣言）の双方が含まれない場合、`decision: "deny"` で実行自体を遮断する。
   - `git push ... origin <branch>`（ブランチ削除 `--delete`/`-d` および `master` を除く）において、ブランチ名に数字（Issue番号）が含まれない場合も `decision: "deny"` で遮断する。
2. **Layer 2: GitHub Actions 必須CIゲート (`.github/workflows/issue-gate.yml` + `src/crawler/package/utils/ci_governance_gate.py` / `enforce_admins: true`)**
   - `.github/workflows/issue-gate.yml` が GitHub REST API（`issues.get`, `pulls.listFiles`）で収集した `{ pr, issue, files }` JSON を標準入出力（`stdin` ➔ `stdout`、外部ファイルパス引数なし）経由で標準ライブラリ完結の `ci_governance_gate.py`（`evaluate_pr_governance()`）へ渡し、`dependabot[bot]` 以外の全 `master` 向け PR に対し以下の4段階検査を実行する：
     - **Gate A (Issue-Driven 一貫性 ＆ 先行起票検査)**:
       - PR本文から `\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s+#(\d+)\b` を抽出し、未記載・対象外（PR番号）・非OPEN（`issue.data.state !== 'open'`）の場合は理由コメント投稿後に `github.rest.pulls.update({ state: 'closed' })` でPRを自動クローズし、`core.setFailed` で失敗させる。
       - PRタイトル先頭 `^\[#(\d+)\]\s+` の番号および作業ブランチ名 `pr.head.ref` 内の独立数値トークンが本文の `issueNumber` と完全一致することを検証する。
       - `new Date(issue.data.created_at).getTime() <= new Date(pr.created_at).getTime()` を検証し、PR作成後に後付けで起票された Issue の紐付けを遮断する。
     - **Gate B (受入基準 ＆ PRチェックリスト完了検査)**:
       - Issue本文のチェックボックス `^[-*]\s*\[([ xX])\]\s*(.*)$` を走査し、定義数0件または `unchecked.length > 0` の場合はマージを遮断する。
       - PR本文（フェンスドコードブロック除外後）に未完了チェックボックス `^[-*]\s*\[\s\]\s*.+$` が残存している場合もマージを遮断する。
     - **Gate C (Spec-Driven / 7大ドメイン正本仕様書必須検査)**:
       - `github.paginate(github.rest.pulls.listFiles, ...)` でPR内の全変更ファイルを取得する。
       - 非テスト実装・インフラ・CI・エージェント領域（`src/**`［`src/crawler/tests/**` 除く］、`terraform/**`、`.github/workflows/**`、`.agents/**`）に変更がある場合、`^docs\/[1-7]_[^/]+\/.+\.md$` に一致する7大ドメイン正本仕様書の変更が1ファイル以上含まれていなければ `core.setFailed` で遮断する。
     - **Gate D (Test-Driven / 単体テスト必須検査)**:
       - 実行コードまたはCIワークフロー（`src/**/*.py`［`src/crawler/tests/**` 除く］、`.agents/scripts/**/*.py`、`.github/workflows/*.yml|*.yaml`）に変更がある場合、`^src\/crawler\/tests\/.+\.py$` に一致するテストファイルの追加・更新が1ファイル以上含まれていなければ `core.setFailed` で遮断する。
3. **Layer 3: アーキテクチャ・ハーネス常時検証 (`src/crawler/tests/unit/test_architecture_harness.py`)**
   - `TestArchitectureHarness` にて `hook_guard.py` と `issue-gate.yml` の上記4大ゲート不変条件が削除・弱体化されていないことを常時アサートする。

## 3. エラーハンドリングおよび終了コード
- 全ステージ合格時: `0`
- いずれかのステージでエラー検知時: `1`
- コンソール出力には、各ステージの成否一覧（絵文字およびサマリーテーブル）と具体的な失敗原因・是正ガイドを出力する。

