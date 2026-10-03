# Review Gate CodeRabbit デッドロック解消および自動 Resolve 化 内部設計書 (Issue #589)

## 1. 改修対象ファイル
- `.github/workflows/review-gate.yml`

## 2. 内部実装詳細

### 2.1 CodeRabbit 指摘スレッドの自動 Resolve 関数
```javascript
async function autoResolveCodeRabbitThreads(unresolvedThreads, headSha, allReviews) {
  // レビュー済みコミットと最新 headSha が異なる CodeRabbit スレッドを特定
  const crReviews = allReviews.filter(r => (r.user?.login || '').toLowerCase().includes('coderabbit'));
  const hasNewCommit = crReviews.some(r => r.commit_id && r.commit_id !== headSha);

  if (!hasNewCommit) return;

  for (const t of unresolvedThreads) {
    const firstComment = t.comments?.nodes?.[0];
    const author = firstComment?.author?.login || '';
    if (author.toLowerCase().includes('coderabbit')) {
      try {
        console.log(`🤖 Auto-resolving CodeRabbit thread ${t.id} after new commit ${headSha.substring(0, 7)}`);
        await github.graphql(`
          mutation($threadId: ID!) {
            resolveReviewThread(input: { threadId: $threadId }) {
              thread { id isResolved }
            }
          }
        `, { threadId: t.id });
        t.isResolved = true;
      } catch (err) {
        console.warn(`Failed to auto-resolve thread ${t.id}: ${err.message}`);
      }
    }
  }
}
```

### 2.2 古い CHANGES_REQUESTED の除外
```javascript
for (const [user, r] of latestReviewByUser.entries()) {
  if (r.state === 'CHANGES_REQUESTED') {
    const isCodeRabbit = user.toLowerCase().includes('coderabbit');
    if (isCodeRabbit && r.commit_id && r.commit_id !== headSha) {
      console.log(`ℹ️ CodeRabbit CHANGES_REQUESTED is obsolete due to newer commit (${r.commit_id.substring(0, 7)} -> ${headSha.substring(0, 7)}). Auto-bypassing.`);
      // staleChangesRequested に入れず、完全にブロック対象から除外
      continue;
    }
    changesRequested.push({ user, reviewId: r.id, commitId: r.commit_id });
  }
}
```

### 2.3 余計なトリガーコメントの削除
- `staleChangesRequested.length > 0 || (hasCodeRabbitUnresolved && ...)` の `issues.createComment` ブロックを完全に除去する。
