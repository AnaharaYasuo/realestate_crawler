# Auto-Release PR Deadlock Fix (#1830)

`dispatch_deploy_after_auto_merge.py` checks `autoMergeRequest` on open release PRs.
When `autoMergeRequest` is `None` (auto-merge is disabled on the repository), `_poll()` returns `"abort"` immediately with exit code `0` instead of waiting 3600s and blocking the release PR from being merged.
