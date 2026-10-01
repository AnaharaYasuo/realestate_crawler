# 変更ファイル動的選別・pre_pr_check 並列最適化 基本設計書 (Issue #579)

## 1. システム構成図
```mermaid
flowchart TD
    Start["git push / task pr-check / pr-create"] --> Classifier["差分ファイル種別分類器<br>(classify_changed_files)"]
    Classifier --> Branch{"変更種別の判定"}

    Branch -->|"Docs / Markdown のみ"| SkipAll["コードテスト・静的解析 全スキップ<br>(所要時間: < 1s)"]
    Branch -->|"Terraform のみ"| IaCOnly["Checkov / IaC 検証のみ実行<br>(pytest / mutation / Sonar スキップ)"]
    Branch -->|"Python / コード変更あり"| Parallel["パイプライン並行ディスパッチ"]

    subgraph ParallelPipe ["並行実行フェーズ (ThreadPoolExecutor)"]
        direction LR
        JobTest["先行キック:<br>pytest (単体・統合テスト)"]
        JobLinter["並行実行:<br>Ruff & SonarCloud"]
        JobSecurity["並行実行:<br>Checkov / actionlint"]
        JobCR{"既存PRあり?<br>gh pr list"}
        JobCR -->|"Yes"| SkipCR["CodeRabbit スキップ"]
        JobCR -->|"No"| ExecCR["CodeRabbit CLI"]
    end

    Parallel --> ParallelPipe
    ParallelPipe --> Join{"全並行ジョブ成功?"}
    Join -->|"No"| FailReport["圧縮エラーサマリー出力<br>(AIトークン節約)"]
    Join -->|"Yes"| MutJob["直列実行:<br>PR Mutation Testing<br>(ファイル書き換え競合防止)"]
    MutJob --> FinalReport["Caveman サマリー出力"]
```

## 2. モジュール設計
1. **`src/crawler/scripts/ops/pre_pr_check.py`**:
   - `classify_changed_files(files)`: `has_python`, `has_terraform`, `has_workflow`, `is_docs_only` を判定。
   - `check_has_open_pr(branch)`: 既存 PR の有無をキャッシュ付きで高速検出。
   - `run_parallel_pipeline()`: 先行 pytest と静的解析・セキュリティの並列実行、完了後の直列 mutation 実行。
   - `format_terse_summary()`: 出力ログを Caveman 形式で要約し、不要なスタックトレースを切り捨てる。
2. **`.githooks/pre-push`**:
   - レートリミット（429）発生時の Soft Fail（Warning 昇格）処理を実装。
   - 既存 PR がある場合の高速検証モード適用。
3. **`.coderabbit.yaml`**:
   - `terraform/**`, `.github/workflows/**` を `path_filters` に追加して除外。
