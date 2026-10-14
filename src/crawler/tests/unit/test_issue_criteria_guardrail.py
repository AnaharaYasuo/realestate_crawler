import pytest
try:
    from scripts.debug_tools.check_issue_criteria import (
        extract_issue_number,
        parse_acceptance_criteria,
        validate_issue_acceptance_criteria,
    )
except ImportError:
    from src.crawler.scripts.debug_tools.check_issue_criteria import (
        extract_issue_number,
        parse_acceptance_criteria,
        validate_issue_acceptance_criteria,
    )


def test_extract_issue_number_from_feature_branch():
    assert extract_issue_number("feature/219-sonar-local-guardrail") == 219
    assert extract_issue_number("fix/42-resolve-parser-bug") == 42
    assert extract_issue_number("feature/issue-105-new-parser") == 105
    assert extract_issue_number("chore/99-update-deps") == 99
    assert extract_issue_number("cursor/123-fix-456") == 123
    assert extract_issue_number("fix/428-eliminate-last-13-sonar-issues") == 428


def test_extract_issue_number_from_commit_message():
    assert extract_issue_number("feature/unlabeled-work", commit_msg="feat: add login (#305)") == 305
    assert extract_issue_number("feature/unlabeled-work", commit_msg="fix: resolve #88") == 88
    assert extract_issue_number("feature/unlabeled-work", commit_msg="Closes #77") == 77


def test_extract_issue_number_not_found():
    assert extract_issue_number("master", commit_msg="update readme") is None
    assert extract_issue_number("random-branch-without-num", commit_msg="foo bar") is None


def test_parse_acceptance_criteria_mixed():
    body = """
## 1. 概要
テスト概要

## 2. アクセプタンスクライテリア (受入基準)
* [x] 【基準1】ユニットテストが作成されていること
* [ ] 【基準2】ドキュメントが更新されていること
- [X] 【基準3】CIが通過すること
- [ ] 【基準4】本番検証完了
"""
    checked, unchecked = parse_acceptance_criteria(body)
    assert len(checked) == 2
    assert len(unchecked) == 2
    assert "【基準1】ユニットテストが作成されていること" in checked
    assert "【基準3】CIが通過すること" in checked
    assert "【基準2】ドキュメントが更新されていること" in unchecked
    assert "【基準4】本番検証完了" in unchecked


def test_parse_acceptance_criteria_no_space():
    body = """
- [x]完了項目
* [ ]未完了項目
"""
    checked, unchecked = parse_acceptance_criteria(body)
    assert len(checked) == 1
    assert checked[0] == "完了項目"
    assert len(unchecked) == 1
    assert unchecked[0] == "未完了項目"


def test_validate_issue_acceptance_criteria_all_checked():
    issue_data = {
        "number": 100,
        "title": "テスト機能",
        "body": """
## 受入基準
* [x] 基準1完了
- [x] 基準2完了
""",
    }
    is_valid, msg, details = validate_issue_acceptance_criteria(issue_data)
    assert is_valid is True
    assert details["checked_count"] == 2
    assert details["unchecked_count"] == 0
    assert "All 2 Acceptance Criteria" in msg


def test_validate_issue_acceptance_criteria_unchecked_fails():
    issue_data = {
        "number": 101,
        "title": "未完了機能",
        "body": """
## 受入基準
* [x] 基準1完了
* [ ] 基準2未完了
""",
    }
    is_valid, msg, details = validate_issue_acceptance_criteria(issue_data)
    assert is_valid is False
    assert details["checked_count"] == 1
    assert details["unchecked_count"] == 1
    assert "1 unchecked" in msg


def test_validate_issue_acceptance_criteria_no_checkboxes_fails():
    issue_data = {
        "number": 102,
        "title": "基準なしIssue",
        "body": """
## 概要
受入基準チェックボックスが定義されていないIssue
""",
    }
    is_valid, msg, details = validate_issue_acceptance_criteria(issue_data)
    assert is_valid is False
    assert details["total_criteria"] == 0
    assert "does not contain any Acceptance Criteria checkboxes" in msg
