# PR事前全検証機構（Pre-PR Check）基本設計書

## 1. システム構成図

```
[開発者 / AIエージェント]
       │
       ▼
   git commit
       │
       ▼
[.githooks/pre-push] ─── (高速水際防御) ───► [Git Push拒否 / 許可]
       │
       ├── Stage 1: ブランチ名/コミットのIssue番号確認
       ├── Stage 2: GitHub Issue実在確認
       ├── Stage 3: check_issue_criteria.py (受入基準チェックボックス全件充足)
       ├── Stage 4: check_local_sonar.py (S3776 <= 15, S8786 ReDoS)
       └── Stage 5: coderabbit review (CodeRabbit CLI レビュー & 指摘検知)
       │
       ▼
 [task pr-check / task pr-create]
       │
       ▼
[pre_pr_check.py] ─── (8大CI相当ローカルゲート)
       ├── Stage 1: Git状態 & ブランチ健全性検査
       ├── Stage 2: GitHub Issue & 受入基準充足判定 (100% checked)
       ├── Stage 3: Ruff Linter & SonarCloud ガードレール
       ├── Stage 4: CodeRabbit CLI ローカルレビュー検証
       ├── Stage 5: Pytest 単体・統合テスト実行
       ├── Stage 6: PR Mutation Testing (キル率 >= 80%)
       ├── Stage 7: セキュリティスキャン (Semgrep / Checkov)
       └── Stage 8: PR メタデータ事前検証 (未チェックボックス不在)
       │
       ├─ [合格 (100%)] ──► gh pr create による安全なPR提出
       └─ [失敗 (Fail)] ──► PR作成中断 ＆ 該当箇所の修正要求
```

## 2. インターフェース設計

### 2.1 CLIインターフェース (`pre_pr_check.py`)
```bash
python src/crawler/scripts/ops/pre_pr_check.py [OPTIONS]

オプション:
  --full            全8ステージ完全実行（デフォルト: True）
  --diff            変更ファイル対象の高速検証モード（Stage 1-4を必須実行）
  --fast            --diff のエイリアス
  --fix             Ruff 等の自動修正を実行
  --skip-tests      テスト実行をスキップ（緊急時用）
  --skip-mutation   ミューテーションテストをスキップ（緊急時用）
  --skip-coderabbit CodeRabbit CLI 検査をスキップ（緊急時・非対応環境用）
  --json            結果をJSON形式で標準出力に出力
```

### 2.2 Taskコマンド仕様 (`Taskfile.yml`)
1. `task pr-check`: `pre_pr_check.py --full` を実行。
2. `task pr-check-fast`: `pre_pr_check.py --diff` を実行。
3. `task coderabbit`: `coderabbit review` を実行。
4. `task sonar-check`: `check_local_sonar.py --diff` を実行。
5. `task pr-create`: `pre_pr_check.py --full` を実行し、合格時のみ PR テンプレートに基づいて `gh pr create` を実行。

## 3. ガードレール遮断方針
| 対象ステージ | 遮断条件 (FAIL) | 是正アクション |
|---|---|---|
| Stage 1: Git & ブランチ | master/production直接、不正ブランチ名、危険一時ファイル | ブランチ作成、不要ファイル削除 |
| Stage 2: Issue & 受入基準 | Issue未存在、`- [ ]` 未チェック残存 | Issue本文を更新して全項目 `- [x]` に |
| Stage 3: Linter & Sonar | Ruffエラー、S3776 > 15、S8786 ReDoS正規表現 | コード整形・リファクタリング |
| Stage 4: CodeRabbit CLI | 未認証・実行エラー、または重大な未解決指摘 | 指摘箇所の修正、`coderabbit auth login` |
| Stage 5: Pytest | いずれかのテスト失敗 | 単体テストまたは本体コード修復 |
| Stage 6: Mutation Testing | キル率 < 80% または Level 1 検知失敗 | テストアサーションの追加・強化 |
| Stage 7: Security Scan | Semgrep ERROR、Checkov FAILED | 脆弱性修正、ポリシー設定 |
| Stage 8: PRメタデータ | PR本文に `- [ ]` 残存、タイトル形式不正 | PRメタデータ・本文の修正 |
