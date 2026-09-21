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
    is_valid, issue_num, msg = validate_branch_name("feature/280-pre-pr-check")
    assert is_valid is True
    assert issue_num == 280

    is_valid, issue_num, msg = validate_branch_name("fix/123-parse-error")
    assert is_valid is True
    assert issue_num == 123


def test_validate_branch_name_invalid():
    """Protected branches and branches without issue numbers should fail."""
    is_valid, issue_num, msg = validate_branch_name("master")
    assert is_valid is False
    assert "保護ブランチ" in msg

    is_valid, issue_num, msg = validate_branch_name("production")
    assert is_valid is False
    assert "保護ブランチ" in msg

    is_valid, issue_num, msg = validate_branch_name("feat-no-issue")
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
