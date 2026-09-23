# CodeRabbit 連携およびレビューコメント解決マージゲート内部設計書 (CodeRabbit & Conversation Resolution Gate Internal Design)

## 1. 概要
本設計書は、GitHub Pull Request における CodeRabbit 自動コードレビューの運用仕様、および指摘コメントへの対応が完了するまでマージをブロックする「会話解決マージゲート」の技術仕様・実装詳細を定めます。

---

## 2. CodeRabbit 設定仕様 (`.coderabbit.yaml`)

リポジトリルートに配置される `.coderabbit.yaml` の構成および各項目の詳細です。

```yaml
# yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json
language: "ja-JP"
early_access: false

reviews:
  profile: "chill"
  request_changes_workflow: true
  high_level_summary: true
  poem: false
  review_status: true
  collapse_walkthrough: false
  # docs / Markdown はコードレビュー対象外（書式・文言ノイズ防止）
  path_filters:
    - "!docs/**"
    - "!**/*.md"
  # パス別レビュー観点（Issue #363）
  path_instructions:
    - path: "src/crawler/package/parser/**"
      instructions: >
        物件種別別 Base（Mansion/Kodate/Tochi/Investment）継承と抽象メソッド実装漏れ、
        フィールド名統一、セレクター堅牢性、1物件1AIリクエスト原則違反を優先して指摘すること。
    - path: "src/crawler/tests/**"
      instructions: >
        Issue 受入基準との対応、アサーションの弱さ（存在確認のみ等）、
        ミューテーション耐性の欠如を優先して指摘すること。
    - path: "src/crawler/scripts/**"
      instructions: >
        外部 API の有限タイムアウト、0件取得失敗分類、パスのハードコード禁止、
        連続タイムアウト Fast-Fail を優先して指摘すること。
  auto_review:
    enabled: true
    drafts: false
    auto_incremental_review: false
    base_branches:
      - "master"
      - "production"
  tools:
    ast-grep:
      enabled: true
    ruff:
      enabled: true
    shellcheck:
      enabled: true
    markdownlint:
      enabled: false

tone_instructions: >
  日本の不動産情報クローラーおよび機械学習価格推定プロジェクトです。
  AGENTS.mdの開発原則（SDD/TDD原則、物件種別別Baseパーサー階層、1物件1AIリクエスト原則等）を尊重し、
  過剰なスタイルの指摘ではなく、潜在的なバグ、型不整合、境界値・欠損値の例外、パフォーマンス劣化、
  セキュリティ上の脆弱性に加え、スケーラビリティと長期保守性を中心に建設的かつ簡潔に指摘してください。

chat:
  auto_reply: true
```

### 設定パラメータの根拠
| パラメータ | 設定値 | 根拠・選定理由 |
| :--- | :--- | :--- |
| `language` | `"ja-JP"` | プロジェクト開発言語・Issue・PRコメントが日本語であるため、日本語で統一。 |
| `profile` | `"chill"` | 瑣末な書式・個人的嗜好の指摘を排除し、クリティカルな不具合・設計ミスに集中。`assertive` は指摘過多で会話解決ゲートを阻害しやすいため不採用（Issue #363）。 |
| `path_instructions` | パーサー / テスト / スクリプト | パスごとに重視観点を固定し、一律レビューでは不足しがちなアーキテクチャ・テスト品質・運用安全の指摘を強化（Issue #363）。 |
| `request_changes_workflow` | `true` | 指摘コメントがある場合に PR に `CHANGES_REQUESTED` を付与し、全指摘が解決（resolved）されると自動で `APPROVED` に遷移させる。 |
| `auto_review.auto_incremental_review` | `false` | PR 初回オープン時のみ自動レビューし、後続 push での再レビュー連鎖（収束不能）を防止。必要時は `@coderabbitai review` で手動起動。 |
| `auto_review.base_branches` | `["master", "production"]` | 開発主幹 (`master`) および本番リリース (`production`) 宛て PR を対象に自動起動。 |
| `path_filters` | `["!docs/**", "!**/*.md"]` | 仕様ドキュメントと Markdown 全般をレビュー対象外とし、マージゲートのノイズを抑制（Issue #345）。 |
| `tone_instructions` | バグ＋長期保守 | 既存の欠陥重視にスケーラビリティ・長期保守性を追加し、フィードバックの質を上げる（Issue #363）。 |
| `tools.markdownlint` | `false` | Markdown 非対象化に整合。コード向け静的解析（`ast-grep`, `ruff`, `shellcheck`）のみ有効。 |
| `tools` | `ast-grep`, `ruff`, `shellcheck` | Python プロジェクト（FastAPI/Flask/Django/Pytest）に適した静的解析を統合。 |

---

## 3. GitHub ブランチ保護によるマージブロック仕様

### 3.1 `required_conversation_resolution`
GitHub ネイティブのブランチ保護機能。
- **対象ブランチ**: `master`, `production`
- **設定値**: `required_conversation_resolution: true`
- **挙動**: PR 内に 1 件でも未解決（Unresolved）の会話スレッドが存在する場合、マージボタンが無効化（ブロック）される。
- **API 設定コマンド**:
  ```bash
  gh api --method PUT repos/:owner/:repo/branches/:branch/protection \
    --input - <<EOF
  {
    "required_status_checks": {
      "strict": true,
      "contexts": [
        "test",
        "Snyk Analysis",
        "Verify All Review Conversations Resolved"
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": null,
    "restrictions": null,
    "required_conversation_resolution": true
  }
  EOF
  ```

---

## 4. CI レビューゲートワークフロー (`.github/workflows/review-gate.yml`)

### 4.1 トリガー仕様および再評価機構
- **イベント**:
  - `pull_request`: `types: [opened, edited, synchronize, reopened]`, `branches: [master, production]`
  - `pull_request_review`: `types: [submitted, edited, dismissed]`
  - `pull_request_review_comment`: `types: [created, edited, deleted]`
  - `issue_comment`: `types: [created, edited, deleted]`
  - `workflow_run`: セキュリティ系ワークフロー（`CodeQL Analysis`, `Security Scan (Trivy, Semgrep, Checkov)`）およびテスト・静的解析ワークフロー（`Parser Tests`, `SonarCloud Analysis`）完了時（再評価）
- **Concurrency**: `group: review-gate-pr-<number>` + `cancel-in-progress: true` で同一 PR の古い実行をキャンセルする。
- **必須ステータス一本化**:
  - Actions ジョブ名は `review-gate-runner`（ブランチ保護の必須チェックにしない）。
  - 必須 context 名は `Verify All Review Conversations Resolved` のみ。
  - 報告は `repos.createCommitStatus` により **常に `pr.head.sha`** へ単一 status を投稿する（ジョブ自動チェックや `checks.create` と同名で二重報告しない）。
  - 同一 context への再投稿は上書きされるため、後続 success/pending が古い failure を置換し、sticky failure を残さない。
- **同一 HEAD SHA での再評価機構 (Re-evaluation Mechanism)**:
  - GitHub では「会話スレッドの解決（Resolve conversation）」単体での GitHub Actions 直接トリガー（Webhookイベント）が存在しない制約があります。
  - また、CodeRabbit がコミットステータス（Commit Status）を `success` に更新した際も直接 Webhook イベントが発火しないため、Gate が初期判定で `pending` に設定された後に取り残される（永久 pending スタック）リスクがあります。
  - そのため、スレッド解決後、チェックボックス更新時、および CodeRabbit レビュー完了後には以下の自動・手動再評価経路を提供します：
    1. **PRコメント/レビュー更新トリガー**: `issue_comment`（コメント投稿・編集・削除）または `pull_request_review` の実行。
    2. **テスト・セキュリティスキャン完了トリガー**: `workflow_run`（`CodeQL Analysis`, `Security Scan`, `Parser Tests`, `SonarCloud Analysis` 完了時）による自動再評価。長尺ジョブ（テスト・SonarCloud）の完了時に CodeRabbit のステータス完了（`success`）を検知して Gate を自動更新。
    3. **GitHub Actions 手動再実行 (Workflow Re-run)**: 開発者が失敗した Gate を再実行（通常は不要。pending は自動で上書きされる）。
- **ブランチフィルタ**: スクリプト冒頭で `pr.base.ref` を判定し、`master` および `production` 宛て以外のPRでは即座にスキップ実行。

### 4.2 未解決スレッド検出ロジック (GraphQL API & ページネーション)
GitHub GraphQL API の `reviewThreads` Connection を利用し、`pageInfo`（`hasNextPage`, `endCursor`）によるカーソルベースのページネーションループですべてのレビュー会話スレッドを走査・収集した上で未解決スレッド（`isResolved: false`）を抽出します。

```graphql
query($owner: String!, $repo: String!, $prNumber: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $prNumber) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          path
          line
          comments(first: 1) {
            nodes {
              author { login }
              body
            }
          }
        }
      }
    }
  }
}
```

### 4.3 未完了チェックボックス検出ロジック
PR本文（`pr.body`）、全レビュー本文（`reviews`）、全PRレビューコメント（`pulls.listReviewComments`）、全PRコメント（`issues.listComments`）を走査し、正規表現 `^[ \t]*[-*][ \t]+\[ \][ \t]*(.*)$` に合致する未完了チェックボックス（`- [ ]`）を抽出します。先頭のインデント（空白・タブ）やネストされたリスト項目を許容しつつ、水平空白のみに限定して誤検知を防止します。

```javascript
// チェックボックス検出正規表現（ネスト・インデント許容、水平空白限定）
const uncheckedRegex = /^[ \t]*[-*][ \t]+\[ \][ \t]*(.*)$/gm;
```

CodeRabbit の自動レビュー内にあるタスク項目（`Fix CodeRabbit comments on this PR` 等）や、PR 概要のタスクリストが未チェックのまま残っている場合、マージ不可対象として記録します。なお、無効化済みのレビュー（`state: DISMISSED`）および CodeRabbit の対話型アクションボタン（`radioGroupId` を含む単体テスト生成トリガー、`Fix all pre-merge checks with AI` 等の自動修復トリガー）はタスクではないため除外判定されます。

### 4.4 CodeRabbit レビューステータス検証ロジック
最新のレビュー状態を照会し、以下を区別して扱う：
1. **待機 (pending)**: CodeRabbit のレビュー実行中（ステータスが `pending` / `in_progress`）。必須 status は `pending`。ジョブは成功終了（failure にしない）。
2. **確定失敗 (failure)**: 最新レビュー状態が `CHANGES_REQUESTED`（変更要求中）。

### 4.5 判定基準と出力
判定結果は次の3状態に分類する。必須 context `Verify All Review Conversations Resolved` へ commit status を投稿し、ジョブ `review-gate-runner` は待機・成功時は成功終了、確定失敗時のみ `setFailed` する。

1. **待機 (pending)**: CodeRabbit 実行中、または必須セキュリティスキャン未開始／実行中。
   - commit status: `pending`
   - ジョブ: SUCCESS（sticky failure を残さない）
2. **確定失敗 (failure)**: 未解決スレッド、未完了チェックボックス、`CHANGES_REQUESTED`、スキャン failure、未解消 Code Scanning アラート、システムエラー。
   - commit status: `failure`
   - ジョブ: FAILED
   - 検出一覧を Actions ログおよび Job Summary に出力
3. **成功 (success)**: 上記いずれにも該当しない。
   - commit status: `success`
   - ジョブ: SUCCESS

---

## 5. 開発者運用フロー（レビューコメント対応手順）

1. **CodeRabbit レビューの確認**:
   - PR **初回オープン後**、数分以内に CodeRabbit が PR Summary およびインラインコメントを投稿（後続 push では自動再レビューされない。`auto_incremental_review: false`）。
2. **指摘事項への対応**:
   - コードの修正が必要な場合: コードを修正して PR ブランチへコミット・プッシュ（追加の自動レビューは行われない。再レビューが必要なら `@coderabbitai review` を手動投稿）。
   - 質問や議論がある場合: インラインコメントに返信（CodeRabbit が自動応答）。
3. **会話スレッドの解決 (Resolve conversation)**:
   - 修正が完了したスレッド、または合意に達したスレッドで「Resolve conversation」ボタンをクリック。
4. **マージゲート解除とマージ実行**:
   - 全スレッドが解決されると、CodeRabbit の `request_changes_workflow` により自動で Approval が付与され、GitHub UI のマージボタンが有効化される。
