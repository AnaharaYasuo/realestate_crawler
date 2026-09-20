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
  auto_review:
    enabled: true
    drafts: false
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
      enabled: true

tone_instructions: >
  日本の不動産情報クローラーおよび機械学習価格推定プロジェクトです。
  AGENTS.mdの開発原則（SDD/TDD原則、物件種別別Baseパーサー階層、1物件1AIリクエスト原則等）を尊重し、
  過剰なスタイルの指摘ではなく、潜在的なバグ、型不整合、境界値・欠損値の例外、パフォーマンス劣化、
  セキュリティ上の脆弱性を中心に建設的かつ簡潔に指摘してください。

chat:
  auto_reply: true
```

### 設定パラメータの根拠
| パラメータ | 設定値 | 根拠・選定理由 |
| :--- | :--- | :--- |
| `language` | `"ja-JP"` | プロジェクト開発言語・Issue・PRコメントが日本語であるため、日本語で統一。 |
| `profile` | `"chill"` | 瑣末な書式・個人的嗜好の指摘を排除し、クリティカルな不具合・設計ミスに集中。 |
| `request_changes_workflow` | `true` | 指摘コメントがある場合に PR に `CHANGES_REQUESTED` を付与し、全指摘が解決（resolved）されると自動で `APPROVED` に遷移させる。 |
| `auto_review.base_branches` | `["master", "production"]` | 開発主幹 (`master`) および本番リリース (`production`) 宛て PR を対象に自動起動。 |
| `tools` | `ast-grep`, `ruff`, etc. | Python プロジェクト（FastAPI/Flask/Django/Pytest）に適した静的解析を統合。 |

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
- **同一 HEAD SHA での再評価機構 (Re-evaluation Mechanism)**:
  - GitHub では「会話スレッドの解決（Resolve conversation）」単体での GitHub Actions 直接トリガー（Webhookイベント）が存在しない制約があります。
  - そのため、スレッド解決後やチェックボックス更新時には以下の再評価経路を提供します：
    1. **PRコメント/レビュー更新トリガー**: `issue_comment`（コメント投稿・編集・削除）または `pull_request_review` の実行。
    2. **GitHub App Webhook 連携 (将来拡張/推奨)**: スレッド解決Webhookを受信したGitHub Appまたはポーリング機構から `repository_dispatch` を発火してワークフローを再実行。
    3. **GitHub Actions 手動再実行 (Workflow Re-run)**: 開発者が失敗した `Verify All Review Conversations Resolved` チェックを再実行。
  - いずれの経路でも、ワークフロー完了時には `github.rest.checks.create` を用いて PR の `head.sha` に対するステータスチェック (`Verify All Review Conversations Resolved`) を直接更新・同期し、コミット再プッシュを行わずにマージ可能状態（PASS）へ遷移させます。
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

CodeRabbit の自動レビュー内にあるタスク項目（`Fix CodeRabbit comments on this PR` 等）や、PR 概要のタスクリストが未チェックのまま残っている場合、マージ不可対象として記録します。

### 4.4 CodeRabbit レビューステータス検証ロジック
最新のレビュー状態を照会し、以下のいずれかに該当する場合はマージ不可と判定します：
1. レビュー状態が `CHANGES_REQUESTED`（変更要求中）であること。
2. CodeRabbit のレビュー実行中（ステータスチェックが `pending` または `in_progress`）であり、完了前に早期マージされようとしていること。

### 4.5 判定基準と出力
1. **未解決スレッド 0 件 かつ 未完了チェックボックス 0 件 かつ レビュー状態正常（Approved または Commented）の場合**:
   - ジョブ成功 (`SUCCESS`)。
   - `✅ All review conversations resolved and all checkboxes checked.` を出力。
2. **未解決スレッド、未完了チェックボックス、または変更要求が存在する場合**:
   - ジョブ失敗 (`FAILED`)。
   - PR のマージを CI ステータスチェック（`Verify All Review Conversations Resolved`）として物理ブロック。
   - 未解決スレッドおよび未完了チェックボックスの一覧（検出元、ファイル名、行番号、内容）を GitHub Actions ログおよび Job Summary に整形出力。

---

## 5. 開発者運用フロー（レビューコメント対応手順）

1. **CodeRabbit レビューの確認**:
   - PR 作成・プッシュ後、数分以内に CodeRabbit が PR Summary およびインラインコメントを投稿。
2. **指摘事項への対応**:
   - コードの修正が必要な場合: コードを修正して PR ブランチへコミット・プッシュ。
   - 質問や議論がある場合: インラインコメントに返信（CodeRabbit が自動応答）。
3. **会話スレッドの解決 (Resolve conversation)**:
   - 修正が完了したスレッド、または合意に達したスレッドで「Resolve conversation」ボタンをクリック。
4. **マージゲート解除とマージ実行**:
   - 全スレッドが解決されると、CodeRabbit の `request_changes_workflow` により自動で Approval が付与され、GitHub UI のマージボタンが有効化される。
