# -*- coding: utf-8 -*-
"""
Unit tests for Pre-PR Check Engine (src/crawler/scripts/ops/pre_pr_check.py).
Validates branch naming, forbidden files, PR metadata, issue criteria, and stage execution.
"""
from scripts.ops.pre_pr_check import (
    validate_branch_name,
    check_forbidden_files,
    validate_pr_metadata_content,
    validate_pr_title_content,
    StageResult,
    PrePRChecker,
)


def test_validate_branch_name_valid():
    """Valid feature and fix branches with issue numbers should pass."""
    is_valid, issue_num, _msg = validate_branch_name("feature/280-pre-pr-check")
    assert is_valid is True
    assert issue_num == 280

    is_valid, issue_num, _msg = validate_branch_name("fix/123-parse-error")
    assert is_valid is True
    assert issue_num == 123


def test_validate_branch_name_invalid():
    """Protected branches and branches without issue numbers should fail."""
    is_valid, _issue_num, msg = validate_branch_name("master")
    assert is_valid is False
    assert "保護ブランチ" in msg

    is_valid, _issue_num, msg = validate_branch_name("production")
    assert is_valid is False
    assert "保護ブランチ" in msg

    is_valid, _issue_num, msg = validate_branch_name("feat-no-issue")
    assert is_valid is False
    assert "Issue 番号" in msg



def test_check_forbidden_files():
    """Accidental or secret files should be flagged."""
    clean_files = [
        "src/crawler/package/parser/mitsuiParser.py",
        "src/crawler/tests/unit/test_mitsui.py",
    ]
    forbidden = check_forbidden_files(clean_files)
    assert len(forbidden) == 0

    dirty_files = [
        "Temp/debug.txt",
        ".env",
        "src/crawler/secret.key",
        "src/crawler/package/__pycache__/foo.pyc",
    ]
    detected = check_forbidden_files(dirty_files)
    assert len(detected) == 4


def test_validate_pr_title_content():
    """PR title must include [#<issue_num>] prefix."""
    assert validate_pr_title_content("[#280] feat: pre-pr-check", 280)[0] is True
    assert validate_pr_title_content("feat: pre-pr-check", 280)[0] is False
    assert validate_pr_title_content("[#281] feat: wrong issue", 280)[0] is False


def test_validate_pr_body_metadata():
    """PR body must contain Closes #<issue_num> and no unchecked checkboxes."""
    valid_body = (
        "Closes #280\n\n"
        "## Summary\nImplemented pre-pr-check.\n\n"
        "* [x] All tests passed\n"
        "* [x] Sonar check passed\n"
    )
    is_valid, msg = validate_pr_metadata_content(valid_body, 280)
    assert is_valid is True

    # Missing Closes #280
    body_no_close = "## Summary\nImplemented pre-pr-check.\n* [x] Done\n"
    is_valid, msg = validate_pr_metadata_content(body_no_close, 280)
    assert is_valid is False
    assert "Closes #280" in msg

    # Unchecked checkbox (- [ ])
    body_unchecked = (
        "Closes #280\n\n"
        "* [x] Criteria 1\n"
        "* [ ] Incomplete criteria\n"
    )
    is_valid, msg = validate_pr_metadata_content(body_unchecked, 280)
    assert is_valid is False
    assert "未完了のチェックボックス" in msg


def test_pre_pr_checker_aggregation():
    """PrePRChecker aggregates stage results and determines overall pass/fail."""
    checker = PrePRChecker()
    r1 = StageResult(stage_id=1, name="Git Check", passed=True, details="OK")
    r2 = StageResult(stage_id=2, name="Issue Check", passed=True, details="OK")
    checker.results = [r1, r2]
    assert checker.is_all_passed() is True
    assert checker.exit_code == 0

    r3 = StageResult(stage_id=3, name="Tests", passed=False, details="Failed", errors=["1 test failed"])
    checker.results.append(r3)
    assert checker.is_all_passed() is False
    assert checker.exit_code == 1


def test_pre_pr_checker_with_branch_and_sha():
    """PrePRChecker respects explicitly supplied branch and sha arguments."""
    checker = PrePRChecker(branch="feature/280-custom-branch", sha="abc1234")
    assert checker.get_current_branch() == "feature/280-custom-branch"
    assert checker.target_sha == "abc1234"


def test_pre_pr_checker_fix_mode_branch(monkeypatch):
    """PrePRChecker passes '--fix' to ruff check when fix_mode=True, and omits it when fix_mode=False."""
    checker_fix = PrePRChecker(fix_mode=True)
    called_cmds = []

    def mock_run_cmd(cmd):
        called_cmds.append(cmd)
        if cmd == ["ruff", "--version"]:
            return 0, "0.16.8", ""
        return 0, "[]", ""

    monkeypatch.setattr(checker_fix, "_run_cmd", mock_run_cmd)
    checker_fix._run_ruff_linter(["src/crawler/foo.py"])
    assert ["ruff", "check", "--fix", "--output-format=json", "src/crawler/foo.py"] in called_cmds

    checker_nofix = PrePRChecker(fix_mode=False)
    called_cmds_nofix = []

    def mock_run_cmd_nofix(cmd):
        called_cmds_nofix.append(cmd)
        if cmd == ["ruff", "--version"]:
            return 0, "0.16.8", ""
        return 0, "[]", ""

    monkeypatch.setattr(checker_nofix, "_run_cmd", mock_run_cmd_nofix)
    checker_nofix._run_ruff_linter(["src/crawler/foo.py"])
    assert ["ruff", "check", "--output-format=json", "src/crawler/foo.py"] in called_cmds_nofix
    assert all("--fix" not in cmd for cmd in called_cmds_nofix)


def test_stage_coderabbit_skipped_by_flag():
    """PrePRChecker skips CodeRabbit stage when skip_coderabbit=True."""
    checker = PrePRChecker(skip_coderabbit=True)
    res = checker.stage_coderabbit()
    assert res.passed is True
    assert "スキップ" in res.details


def test_stage_coderabbit_cli_not_installed(monkeypatch):
    """PrePRChecker fails when coderabbit CLI is not installed."""
    checker = PrePRChecker(skip_coderabbit=False)

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 1, "", "command not found"
        return 0, "", ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("インストール" in e for e in res.errors)


def test_stage_coderabbit_success_clean(monkeypatch):
    """PrePRChecker passes when CodeRabbit CLI succeeds with no findings."""
    checker = PrePRChecker(skip_coderabbit=False)

    agent_output = (
        '{"type":"status","phase":"setup","status":"review_skipped","message":"No changes"}\n'
        '{"type":"complete","status":"review_skipped","findings":0,"message":"No changes"}'
    )

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        return 0, agent_output, ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    monkeypatch.setattr(checker, "get_changed_files", list)

    res = checker.stage_coderabbit()
    assert res.passed is True
    assert "指摘: 0件" in res.details


def test_stage_coderabbit_with_findings(monkeypatch):
    """PrePRChecker fails when CodeRabbit returns review findings."""
    checker = PrePRChecker(skip_coderabbit=False)

    agent_output = (
        '{"type":"finding","severity":"high","message":"Potential SQL injection vulnerability","file":"src/crawler/parser.py","line":42}\n'
        '{"type":"complete","status":"completed","findings":1,"message":"Review completed"}'
    )

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        return 0, agent_output, ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("指摘" in e for e in res.errors)


def test_stage_coderabbit_major_finding_fails(monkeypatch):
    """PrePRChecker fails when CodeRabbit returns a MAJOR severity finding."""
    checker = PrePRChecker(skip_coderabbit=False)

    agent_output = (
        '{"type":"finding","severity":"major","fileName":"src/crawler/app.py","line":10,"message":"Timeout missing"}\n'
        '{"type":"complete","status":"completed","findings":1,"message":"Review completed"}'
    )

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        return 0, agent_output, ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("[MAJOR]" in e for e in res.errors)


def test_stage_coderabbit_timeout(monkeypatch):
    """PrePRChecker fails when CodeRabbit execution times out."""
    checker = PrePRChecker(skip_coderabbit=False)

    def mock_run_cmd(cmd, **kwargs):
        if cmd == ["coderabbit", "--version"]:
            assert kwargs.get("timeout") == 30.0
            return 0, "0.8.1", ""
        if cmd[0] == "git":
            return 0, "merge_base_sha", ""
        assert 1700.0 <= kwargs.get("timeout", 0.0) <= 1800.0
        return 124, "", "コマンドがタイムアウトしました (1800秒)"

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("タイムアウト" in e for e in res.errors)


def test_stage_coderabbit_with_target_sha(tmp_path, monkeypatch):
    """PrePRChecker invokes coderabbit with merge-base and finite timeout when target_sha is provided."""
    checker = PrePRChecker(skip_coderabbit=False, sha="abc1234")
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))
    executed_cmds = []

    def mock_run_cmd(cmd, **kwargs):
        executed_cmds.append((cmd, kwargs))
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd == ["git", "rev-parse", "HEAD"] or cmd == ["git", "rev-parse", "abc1234"]:
            return 0, "abc1234", ""
        if cmd == ["git", "merge-base", "origin/master", "abc1234"]:
            return 0, "base_commit_hash", ""
        return 0, '{"type":"complete","status":"completed","findings":0}', ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is True

    review_call = next(c for c, kw in executed_cmds if "review" in c)
    review_kw = next(kw for c, kw in executed_cmds if "review" in c)
    assert "--base-commit" in review_call
    assert "base_commit_hash" in review_call
    assert "--committed" in review_call
    assert 1700.0 <= review_kw.get("timeout", 0.0) <= 1800.0


def test_get_changed_files_diff_error(monkeypatch):
    """PrePRChecker stages fail if both origin/master and master diffs fail."""
    checker = PrePRChecker(branch="feature/506-test")

    def mock_run_cmd(cmd, **_kwargs):
        if "diff" in cmd:
            return 1, "", "fatal: ambiguous argument 'origin/master'"
        return 0, "", ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    r1 = checker.stage1_git_and_branch()
    assert r1.passed is False
    assert any("変更ファイル差分の取得に失敗しました" in e for e in r1.errors)

    r3 = checker.stage3_linter_and_sonar()
    assert r3.passed is False
    assert any("変更ファイル差分の取得に失敗しました" in e for e in r3.errors)

    r7 = checker.stage7_security()
    assert r7.passed is False
    assert any("変更ファイル差分の取得に失敗しました" in e for e in r7.errors)


def test_stage_coderabbit_rate_limit_warning(tmp_path, monkeypatch):
    """PrePRChecker passes with warning when CodeRabbit returns rate limit error."""
    checker = PrePRChecker(skip_coderabbit=False)
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))

    rate_limit_output = (
        '{"type":"error","errorType":"rate_limit","message":"Rate limit exceeded","recoverable":true}\n'
    )

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd[0] == "git":
            return 0, "base_commit_sha", ""
        return 1, rate_limit_output, "Error: Rate limit exceeded"

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is True
    assert any("利用制限" in w or "Rate limit" in w for w in res.warnings)


def test_stage_coderabbit_ordinary_json_error_fails(tmp_path, monkeypatch):
    """PrePRChecker fails when CodeRabbit returns an ordinary non-rate-limit error."""
    checker = PrePRChecker(skip_coderabbit=False)
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd[0] == "git":
            return 0, "base_commit_sha", ""
        return 1, '{"type":"error","message":"Internal server error"}', "Fatal crash"

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("Internal server error" in e for e in res.errors)


def test_stage_coderabbit_abnormal_completion_fails(tmp_path, monkeypatch):
    """PrePRChecker fails when completion status is abnormal."""
    checker = PrePRChecker(skip_coderabbit=False)
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd[0] == "git":
            return 0, "base_commit_sha", ""
        return 0, '{"type":"complete","status":"failed_abnormal"}', ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("failed_abnormal" in e for e in res.errors)


def test_stage_coderabbit_non_json_rate_limit_with_rc_zero_not_skipped(tmp_path, monkeypatch):
    """rc=0 with random rate-limit word in non-json output does not bypass completion check."""
    checker = PrePRChecker(skip_coderabbit=False)
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd[0] == "git":
            return 0, "base_commit_sha", ""
        # rc=0 but no completion event, only stdout mentions 'rate limit'
        return 0, "Some random log mentioning rate limit", ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)
    res = checker.stage_coderabbit()
    assert res.passed is False
    assert any("完了イベントを受信できませんでした" in e for e in res.errors)


def test_stage_coderabbit_cache_skip_on_subsequent_runs(tmp_path, monkeypatch):
    """同一ブランチで既にレビュー完了マーカーが存在する場合はスキップされること."""
    checker = PrePRChecker(skip_coderabbit=False)
    monkeypatch.setattr(checker, "repo_root", str(tmp_path))
    monkeypatch.setattr(checker, "get_current_branch", lambda: "feature/test-branch")

    def mock_run_cmd(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        return 0, "", ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_cmd)

    # 初回前にマーカー作成
    cache_dir = tmp_path / ".coderabbit_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    marker = cache_dir / "feature_test-branch.reviewed"
    marker.write_text("reviewed", encoding="utf-8")
    marker_sha = cache_dir / "feature_test-branch_headcomm.reviewed"
    marker_sha.write_text("reviewed", encoding="utf-8")

    def mock_run_sha(cmd, **_kwargs):
        if cmd == ["coderabbit", "--version"]:
            return 0, "0.8.1", ""
        if cmd == ["git", "rev-parse", "HEAD"]:
            return 0, "headcommit123", ""
        return 0, "", ""

    monkeypatch.setattr(checker, "_run_cmd", mock_run_sha)

    res = checker.stage_coderabbit()
    assert res.passed is True
    assert "CodeRabbitレビュー済み" in res.details
    assert any("スキップ" in w for w in res.warnings)






