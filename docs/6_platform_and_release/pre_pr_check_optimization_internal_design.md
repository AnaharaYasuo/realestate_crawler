# 変更ファイル動的選別・pre_pr_check 並列最適化 内部設計書 (Issue #579)

## 1. クラスおよびデータ構造設計

### 1.1 `FileCategory` (データクラス)
```python
@dataclass
class FileCategory:
    has_python: bool = False
    has_terraform: bool = False
    has_workflow: bool = False
    has_docs: bool = False
    is_docs_only: bool = False
    is_tf_only: bool = False
    changed_count: int = 0
```

### 1.2 `classify_changed_files(files: list[str]) -> FileCategory`
- 拡張子およびパスパターンマッチング：
  - `.py` ➔ `has_python = True`
  - `terraform/` または `.tf` ➔ `has_terraform = True`
  - `.github/workflows/` または `.yml`/`.yaml` ➔ `has_workflow = True`
  - `.md` または `docs/` ➔ `has_docs = True`
- フラグ算出：
  - `is_docs_only = has_docs and not (has_python or has_terraform or has_workflow)`
  - `is_tf_only = has_terraform and not (has_python or has_workflow or has_docs)`

### 1.3 `has_open_pr(branch: str) -> bool`
- `gh pr list --head <branch> --state open --json number` を実行。
- タイムアウトは 5.0 秒。取得結果が 1 件以上あれば `True`。

### 1.4 並行パイプライン実行ロジック
```python
def run_all(self, title: str | None = None, body: str | None = None) -> bool:
    # 1. Git & ブランチ健全性 (直列)
    # 2. Issue 受入基準 (直列)
    # 3. 差分ファイル分類
    category = classify_changed_files(self.changed_files)
    
    # 4. ドキュメントのみなら全スキップで完了
    if category.is_docs_only:
        return True

    # 5. 並列実行対象ステージの収集
    futures = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        if category.has_python and not self.diff_mode:
            futures["tests"] = executor.submit(self.stage5_tests)
        if category.has_python:
            futures["linter_sonar"] = executor.submit(self.stage3_linter_and_sonar)
        if not self.skip_coderabbit and not self.has_open_pr:
            futures["coderabbit"] = executor.submit(self.stage_coderabbit)
        if category.has_terraform or category.has_workflow:
            futures["security"] = executor.submit(self.stage7_security)

    # 6. ミューテーションテストの直列実行 (テスト成功時のみ)
    if "tests" in futures and futures["tests"].result().passed and not self.diff_mode:
        self.results.append(self.stage6_mutation())
```

### 1.5 トークン圧縮サマリー (`print_summary`)
- 各ステージのエラー出力は最大 3 件、各 120 文字以内でトランケート。
- スタックトレース中の `Traceback` や余分な空行を除去し、`File "...", line X: ErrorMessage` のみ保持。
