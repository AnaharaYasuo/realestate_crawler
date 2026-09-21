# PR事前全検証機構（Pre-PR Check）内部設計仕様書

## 1. モジュール配置
- 検証本体スクリプト: `src/crawler/scripts/ops/pre_pr_check.py`
- 単体テスト: `src/crawler/tests/unit/test_pre_pr_check.py`
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
- `check_local_sonar.scan_file` を用いて、S3776 (Cognitive Complexity <= 15) および S8786 (ReDoS Regex Risk) を高速検証

#### Stage 4: `run_pytest_suite()`
- 変更差分に基づき、テスト対象を特定
- `pytest -n auto src/crawler/tests/unit/` を実行
- テスト失敗件数 == 0 をアサート

#### Stage 5: `run_mutation_testing()`
- `src.crawler.scripts.run_mutation_testing` の PR モード (`--pr-mode --threshold=80`) を実行
- キル率 (Mutation Score) >= 80% をアサート

#### Stage 6: `run_security_scan()`
- Python ファイル変更時: Semgrep スキャン
- Terraform ファイル変更時: Checkov スキャン

#### Stage 7: `validate_pr_metadata()`
- PR タイトル形式 (`[#<issue_num>] ...`)
- PR 本文の `Closes #<issue_num>` 存在確認
- PR 本文中の `- [ ]` 残存検知（GitHub Actions Review Gate と同様の正規表現ロジック）

## 3. エラーハンドリングおよび終了コード
- 全ステージ合格時: `0`
- いずれかのステージでエラー検知時: `1`
- コンソール出力には、各ステージの成否一覧（絵文字およびサマリーテーブル）と具体的な失敗原因・是正ガイドを出力する。
