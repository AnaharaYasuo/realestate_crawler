# Issue #1585: AIエージェントによるテスト改ざん防止ガードレール 仕様書

## 1. 概要 (Overview)
『プロダクト品質管理の実践ガイド』第19章（19.3 テスト改ざんの防止技術）に基づき、AIエージェントがテストを通すために既存テストのアサーションを緩めたり、`pytest.mark.skip` を追加・テスト削除を行うリスク（Reward Hacking）を機械的に防止する。

## 2. ガードレール仕様 (Guard Specifications)
- `.agents/scripts/hook_guard.py` にテスト改ざん検知ロジックを追加：
  1. `git diff` によりテストファイル（`tests/` 配下）の変更差分を走査。
  2. `@pytest.mark.skip`, `@pytest.mark.xfail`, `unittest.skip` 等の新規追加行（`+` で始まる行）を検知した場合にブロック。
  3. `assert` 文の大規模削除または無力化（`assert True` 等）を検知した場合に拒絶。
- 違反時は `Pre-commit hook rejected: Test tampering detected` として exit code 1 で停止。

## 3. テスト計画 (TDD)
- `src/crawler/tests/test_hook_guard_tamper.py` において：
  - 改ざん（skip追加やアサーション無力化）をシミュレートした diff を与えて正しく例外・拒絶されることを検証。
  - 正常なテスト追加・修正の diff ではブロックされず通過することを検証。
