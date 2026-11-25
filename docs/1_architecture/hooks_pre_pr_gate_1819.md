# Hooks Pre-PR Gate (#1819)

`hook_guard.py` enforces the following checks before `gh pr create` to prevent CI-time rejections:
1. **SDD Gate**: `docs/1_...` through `docs/7_.../*.md` specification update must be included.
2. **TDD Gate**: When modifying non-test files under `src/`, unit test additions/updates under `src/crawler/tests/**/*.py` must be included.
3. **Issue Acceptance Criteria Gate**: The linked GitHub Issue must define at least one Acceptance Criteria checkbox (`- [ ]` or `- [x]`).
