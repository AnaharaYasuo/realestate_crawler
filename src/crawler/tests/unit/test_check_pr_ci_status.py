from scripts.debug_tools.check_pr_ci_status import (
    CheckCategory,
    classify_check_status,
    evaluate_checks_summary,
    parse_pr_checks_output,
)


def test_classify_check_status():
    assert classify_check_status("pass") == CheckCategory.PASSED
    assert classify_check_status("success") == CheckCategory.PASSED
    assert classify_check_status("skipping") == CheckCategory.PASSED

    assert classify_check_status("pending") == CheckCategory.PENDING
    assert classify_check_status("in_progress") == CheckCategory.PENDING
    assert classify_check_status("queued") == CheckCategory.PENDING

    assert classify_check_status("action_required") == CheckCategory.BLOCKED
    assert classify_check_status("cancelled") == CheckCategory.BLOCKED

    assert classify_check_status("fail") == CheckCategory.FAILED
    assert classify_check_status("failure") == CheckCategory.FAILED


def test_parse_pr_checks_output():
    sample_output = """Checkov\tpass\t3s\thttps://github.com/runs/1\t
CodeQL\tpending\t0\thttps://github.com/runs/2\t
Test (Unit Tests)\tfail\t1m\thttps://github.com/runs/3\t
Verify Source Branch\taction_required\t0\thttps://github.com/runs/4\t
"""
    parsed = parse_pr_checks_output(sample_output)
    assert len(parsed[CheckCategory.PASSED]) == 1
    assert parsed[CheckCategory.PASSED][0]["name"] == "Checkov"

    assert len(parsed[CheckCategory.PENDING]) == 1
    assert parsed[CheckCategory.PENDING][0]["name"] == "CodeQL"

    assert len(parsed[CheckCategory.FAILED]) == 1
    assert parsed[CheckCategory.FAILED][0]["name"] == "Test (Unit Tests)"

    assert len(parsed[CheckCategory.BLOCKED]) == 1
    assert parsed[CheckCategory.BLOCKED][0]["name"] == "Verify Source Branch"


def test_evaluate_checks_summary_all_passed():
    categories = {
        CheckCategory.PASSED: [{"name": "Checkov"}, {"name": "CodeQL"}],
        CheckCategory.PENDING: [],
        CheckCategory.FAILED: [],
        CheckCategory.BLOCKED: [],
    }
    result = evaluate_checks_summary(categories)
    assert result["status"] == "SUCCESS"
    assert result["can_merge"] is True


def test_evaluate_checks_summary_has_failed():
    categories = {
        CheckCategory.PASSED: [{"name": "Checkov"}],
        CheckCategory.PENDING: [],
        CheckCategory.FAILED: [{"name": "Test (Unit Tests)", "url": "https://github.com/runs/3"}],
        CheckCategory.BLOCKED: [],
    }
    result = evaluate_checks_summary(categories)
    assert result["status"] == "FAILURE"
    assert result["can_merge"] is False


def test_evaluate_checks_summary_has_blocked():
    categories = {
        CheckCategory.PASSED: [{"name": "Checkov"}],
        CheckCategory.PENDING: [],
        CheckCategory.FAILED: [],
        CheckCategory.BLOCKED: [{"name": "Production Gate", "url": "https://github.com/runs/4"}],
    }
    result = evaluate_checks_summary(categories)
    assert result["status"] == "BLOCKED"
    assert result["can_merge"] is False


def test_evaluate_checks_summary_has_pending():
    categories = {
        CheckCategory.PASSED: [{"name": "Checkov"}],
        CheckCategory.PENDING: [{"name": "Integration Tests"}],
        CheckCategory.FAILED: [],
        CheckCategory.BLOCKED: [],
    }
    result = evaluate_checks_summary(categories)
    assert result["status"] == "PENDING"
    assert result["can_merge"] is False
