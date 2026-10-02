# Review Gate CodeRabbit デッドロック解消および自動 Resolve 化 要件定義書 (Issue #589)

## 1. 概要と背景
`auto_incremental_review: false` の運用下において、PR 作成後の修正コミット push 時に CodeRabbit が自動再レビューを行わないため、`.github/workflows/review-gate.yml` が古い `CHANGES_REQUESTED` の再評価を待ち続けて `PENDING` となり、PR が永久に膠着する。本要件はこれを解消し、人間の手動 Resolve 操作なしに完全自動で Gate を通過可能にする仕様を定める。

## 2. 機能要件 (FR)
- **FR-001 (古い CHANGES_REQUESTED の自動失効)**:
  - レビュー時点のコミット（`r.commit_id`）より新しいコミット（`headSha`）が存在する場合、CodeRabbit の `CHANGES_REQUESTED` は修正コミットにより対応済みとみなし、Gate のブロック要因（硬性失敗・保留）から自動除外すること。
- **FR-002 (CodeRabbit 指摘スレッドの自動 Resolve)**:
  - 新コミット（`headSha != r.commit_id`）が push された際、CodeRabbit が起票した未解決スレッド（`unresolved threads`）が存在する場合、Gate スクリプトが GitHub GraphQL API (`resolveReviewThread`) を呼び出して自動的に「解決済み (Resolved)」へ遷移させること。
- **FR-003 (余計なレビュー連投コメントの撤去)**:
  - `review-gate.yml` 内で `@coderabbitai review` を PR に自動投稿していた処理を撤去し、コメント爆撃および無駄な再レビュー待機を防止すること。
- **FR-004 (CI 通過時の即座マージ可能保証)**:
  - 全テスト（Parser Tests 等）およびセキュリティスキャンが通過している場合、人間の操作なしに `Verify All Review Conversations Resolved` が即座に `SUCCESS` に遷移すること。

## 3. 非機能要件 (NFR)
- **NFR-001 (安全弁の維持)**: 人間レビュアー（CodeRabbit 以外）による `CHANGES_REQUESTED` や未解決スレッドは自動解決せず、人間のレビュー承認権限を保護すること。
- **NFR-002 (冪等性)**: 既に解決済みのスレッドに対して `resolveReviewThread` を重複実行してもエラーにならず正常終了すること。
