import subprocess
from unittest.mock import MagicMock, patch

from scripts.debug_tools.check_pr_ci_status import (
    CheckCategory,
    classify_check_status,
    evaluate_checks_summary,
    fetch_pr_checks,
    parse_pr_checks_output,
    poll_pr_checks,
)


def test_classify_check_status_comprehensive():
    # Positive statuses
    assert classify_check_status("pass") == CheckCategory.PASSED
    assert classify_check_status("success") == CheckCategory.PASSED
    assert classify_check_status("skipping") == CheckCategory.PASSED
    assert classify_check_status("skipped") == CheckCategory.PASSED
    assert classify_check_status("neutral") == CheckCategory.PASSED
    # Normalization with whitespace & uppercase
    assert classify_check_status("  PASS  ") == CheckCategory.PASSED
    assert classify_check_status("SUCCESS") == CheckCategory.PASSED

    # Pending
    assert classify_check_status("pending") == CheckCategory.PENDING
    assert classify_check_status("in_progress") == CheckCategory.PENDING
    assert classify_check_status("queued") == CheckCategory.PENDING

    # Blocked
    assert classify_check_status("action_required") == CheckCategory.BLOCKED
    assert classify_check_status("cancelled") == CheckCategory.BLOCKED
    assert classify_check_status("stalled") == CheckCategory.BLOCKED

    # Failure / Empty / Unknown
    assert classify_check_status("fail") == CheckCategory.FAILED
    assert classify_check_status("failure") == CheckCategory.FAILED
    assert classify_check_status("") == CheckCategory.FAILED
    assert classify_check_status("unknown_custom_failure") == CheckCategory.FAILED


def test_parse_pr_checks_output_all_fields():
    sample_output = (
        "Checkov\tpass\t3s\thttps://github.com/runs/1\n"
        "CodeQL\tpending\t12s\thttps://github.com/runs/2\n"
        "Test (Unit Tests)\tfail\t1m\thttps://github.com/runs/3\n"
        "Verify Source Branch\taction_required\t0s\thttps://github.com/runs/4\n"
    )
    parsed = parse_pr_checks_output(sample_output)

    # Check PASSED
    assert len(parsed[CheckCategory.PASSED]) == 1
    assert parsed[CheckCategory.PASSED][0] == {
        "name": "Checkov",
        "status": "pass",
        "duration": "3s",
        "url": "https://github.com/runs/1",
    }

    # Check PENDING
    assert len(parsed[CheckCategory.PENDING]) == 1
    assert parsed[CheckCategory.PENDING][0] == {
        "name": "CodeQL",
        "status": "pending",
        "duration": "12s",
        "url": "https://github.com/runs/2",
    }

    # Check FAILED
    assert len(parsed[CheckCategory.FAILED]) == 1
    assert parsed[CheckCategory.FAILED][0] == {
        "name": "Test (Unit Tests)",
        "status": "fail",
        "duration": "1m",
        "url": "https://github.com/runs/3",
    }

    # Check BLOCKED
    assert len(parsed[CheckCategory.BLOCKED]) == 1
    assert parsed[CheckCategory.BLOCKED][0] == {
        "name": "Verify Source Branch",
        "status": "action_required",
        "duration": "0s",
        "url": "https://github.com/runs/4",
    }


def test_evaluate_checks_summary_precedence_and_counts():
    # Empty
    empty_res = evaluate_checks_summary({})
    assert empty_res["status"] == "NO_CHECKS"
    assert empty_res["can_merge"] is False
    assert empty_res["counts"]["total"] == 0

    # All passed
    pass_res = evaluate_checks_summary({
        CheckCategory.PASSED: [{"name": "A"}, {"name": "B"}],
        CheckCategory.PENDING: [],
        CheckCategory.FAILED: [],
        CheckCategory.BLOCKED: [],
    })
    assert pass_res["status"] == "SUCCESS"
    assert pass_res["can_merge"] is True
    assert pass_res["counts"]["passed"] == 2
    assert pass_res["counts"]["total"] == 2

    # Mixed: FAILED takes precedence over BLOCKED and PENDING
    mixed_res = evaluate_checks_summary({
        CheckCategory.PASSED: [{"name": "A"}],
        CheckCategory.PENDING: [{"name": "B"}],
        CheckCategory.BLOCKED: [{"name": "C"}],
        CheckCategory.FAILED: [{"name": "D"}],
    })
    assert mixed_res["status"] == "FAILURE"
    assert mixed_res["can_merge"] is False
    assert mixed_res["counts"]["total"] == 4

    # Mixed: BLOCKED takes precedence over PENDING
    blocked_res = evaluate_checks_summary({
        CheckCategory.PASSED: [{"name": "A"}],
        CheckCategory.PENDING: [{"name": "B"}],
        CheckCategory.BLOCKED: [{"name": "C"}],
        CheckCategory.FAILED: [],
    })
    assert blocked_res["status"] == "BLOCKED"
    assert blocked_res["can_merge"] is False


def test_fetch_pr_checks_mocks():
    # 1. subprocess.TimeoutExpired
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10.0)):
        ret, stdout, stderr = fetch_pr_checks(604, timeout=10.0)
        assert ret == 124
        assert "timed out" in stderr

    # 2. FileNotFoundError -> fallback to API
    with patch("subprocess.run", side_effect=FileNotFoundError("gh not found")), \
         patch("scripts.debug_tools.check_pr_ci_status._fetch_pr_checks_via_api", return_value=(0, "mocked\tpass\t0s\turl", "")) as mock_api:
        ret, stdout, stderr = fetch_pr_checks(604, timeout=10.0)
        assert ret == 0
        assert "mocked" in stdout
        assert mock_api.called

    # 3. Nonzero exit with nonempty stdout (gh CLI output retained)
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = "Checkov\tfail\t0s\thttps://..."
    mock_res.stderr = ""
    with patch("subprocess.run", return_value=mock_res):
        ret, stdout, stderr = fetch_pr_checks(604, timeout=10.0)
        assert ret == 1
        assert "Checkov" in stdout


def test_poll_pr_checks_timeout_and_no_sleep_on_final_attempt():
    with patch("scripts.debug_tools.check_pr_ci_status.fetch_pr_checks", return_value=(0, "Check\tpending\t0s\turl", "")), \
         patch("time.sleep") as mock_sleep:
        res = poll_pr_checks(604, max_attempts=3, interval=5)
        assert res["final_status"] == "TIMEOUT"
        assert res["can_merge"] is False
        assert res["attempts"] == 3
        # time.sleep called for attempt 1 and 2, but NOT after attempt 3
        assert mock_sleep.call_count == 2


def test_poll_pr_checks_consecutive_timeouts_circuit_breaker():
    # Circuit breaker triggers after 3 consecutive timeouts (MAX_CONSECUTIVE_TIMEOUTS = 3)
    with patch("scripts.debug_tools.check_pr_ci_status.fetch_pr_checks", return_value=(124, "", "Timed out after 10.0s")), \
         patch("time.sleep") as mock_sleep:
        res = poll_pr_checks(604, max_attempts=10, interval=5)
        assert res["final_status"] == "RETRIEVAL_ERROR"
        assert res["can_merge"] is False
        assert res["attempts"] == 3
        assert "Circuit breaker" in res["error"]
        assert mock_sleep.call_count == 2  # slept after attempt 1 and 2, exited on attempt 3


def test_poll_pr_checks_consecutive_timeouts_resets_on_success():
    # If a timeout occurs, but next is successful, counter resets
    responses = [
        (124, "", "Timed out"),
        (124, "", "Timed out"),
        (0, "Check\tpending\t0s\turl", ""),  # resets consecutive timeout
        (124, "", "Timed out"),
        (0, "Check\tpass\t0s\turl", ""),     # passes
    ]
    with patch("scripts.debug_tools.check_pr_ci_status.fetch_pr_checks", side_effect=responses), \
         patch("time.sleep"):
        res = poll_pr_checks(604, max_attempts=10, interval=5)
        assert res["final_status"] == "SUCCESS"
        assert res["can_merge"] is True
        assert res["attempts"] == 5


def test_poll_pr_checks_permanent_http_error_immediate_return():
    # HTTP 401/403/404 returns ret == 2, returning RETRIEVAL_ERROR immediately without retry
    with patch("scripts.debug_tools.check_pr_ci_status.fetch_pr_checks", return_value=(2, "", "Permanent HTTP 404 error: Not Found")), \
         patch("time.sleep") as mock_sleep:
        res = poll_pr_checks(604, max_attempts=5, interval=10)
        assert res["final_status"] == "RETRIEVAL_ERROR"
        assert res["can_merge"] is False
        assert res["attempts"] == 1
        assert "Permanent HTTP 404 error" in res["error"]
        assert mock_sleep.call_count == 0
