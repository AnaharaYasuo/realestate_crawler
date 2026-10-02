#!/usr/bin/env python3
"""
PR CI Status Inspector and Finite-Timeout Monitor (check_pr_ci_status.py)

Issue #602: Enforces finite timeouts and non-blocking polling on GitHub Actions CI checks,
banning unlimited `--watch` commands that hang on action_required or queued jobs.
"""
import argparse
import json
import logging
import re
import subprocess
import sys
import time
from enum import Enum
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_pr_ci_status")

DEFAULT_CLI_TIMEOUT: float = 10.0
MAX_CLI_TIMEOUT: float = 10.0


class CheckCategory(str, Enum):
    PASSED = "passed"
    PENDING = "pending"
    FAILED = "failed"
    BLOCKED = "blocked"


def classify_check_status(raw_status: str) -> CheckCategory:
    """Classify GitHub checks status into four main categories."""
    status = (raw_status or "").strip().lower()
    if status in ("pass", "success", "skipping"):
        return CheckCategory.PASSED
    if status in ("pending", "in_progress", "queued"):
        return CheckCategory.PENDING
    if status in ("action_required", "cancelled"):
        return CheckCategory.BLOCKED
    return CheckCategory.FAILED


def parse_pr_checks_output(output: str) -> dict[CheckCategory, list[dict[str, str]]]:
    """Parse text output of `gh pr checks <PR_NUM>`."""
    categories: dict[CheckCategory, list[dict[str, str]]] = {
        CheckCategory.PASSED: [],
        CheckCategory.PENDING: [],
        CheckCategory.FAILED: [],
        CheckCategory.BLOCKED: [],
    }

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line) if p.strip()]
        if not parts:
            continue

        name = parts[0]
        status = parts[1] if len(parts) > 1 else "unknown"
        duration = parts[2] if len(parts) > 2 else ""
        url = parts[3] if len(parts) > 3 else ""

        category = classify_check_status(status)
        categories[category].append({
            "name": name,
            "status": status,
            "duration": duration,
            "url": url,
        })

    return categories


def evaluate_checks_summary(categories: dict[CheckCategory, list[dict[str, str]]]) -> dict[str, Any]:
    """Evaluate overall status from parsed categories."""
    passed_cnt = len(categories.get(CheckCategory.PASSED, []))
    pending_cnt = len(categories.get(CheckCategory.PENDING, []))
    failed_cnt = len(categories.get(CheckCategory.FAILED, []))
    blocked_cnt = len(categories.get(CheckCategory.BLOCKED, []))
    total_cnt = passed_cnt + pending_cnt + failed_cnt + blocked_cnt

    if total_cnt == 0:
        return {
            "status": "NO_CHECKS",
            "can_merge": False,
            "counts": {"passed": 0, "pending": 0, "failed": 0, "blocked": 0, "total": 0},
        }

    if failed_cnt > 0:
        status_code = "FAILURE"
        can_merge = False
    elif blocked_cnt > 0:
        status_code = "BLOCKED"
        can_merge = False
    elif pending_cnt > 0:
        status_code = "PENDING"
        can_merge = False
    else:
        status_code = "SUCCESS"
        can_merge = True

    return {
        "status": status_code,
        "can_merge": can_merge,
        "counts": {
            "passed": passed_cnt,
            "pending": pending_cnt,
            "failed": failed_cnt,
            "blocked": blocked_cnt,
            "total": total_cnt,
        },
    }


def fetch_pr_checks(pr_number: int, timeout: float = DEFAULT_CLI_TIMEOUT) -> tuple[int, str, str]:
    """Execute `gh pr checks <PR_NUM>` with finite timeout limit (max 10s)."""
    bounded_timeout = min(timeout, MAX_CLI_TIMEOUT)
    try:
        res = subprocess.run(
            ["gh", "pr", "checks", str(pr_number)],
            capture_output=True,
            text=True,
            timeout=bounded_timeout,
            check=False,
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {bounded_timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def poll_pr_checks(
    pr_number: int,
    max_attempts: int = 20,
    interval: int = 15,
    cli_timeout: float = DEFAULT_CLI_TIMEOUT,
) -> dict[str, Any]:
    """Poll PR CI checks with finite timeouts and intervals."""
    logger.info(
        "Starting finite-timeout CI monitoring for PR #%d (max_attempts=%d, interval=%ds, timeout=%.1fs)",
        pr_number,
        max_attempts,
        interval,
        cli_timeout,
    )

    for attempt in range(1, max_attempts + 1):
        ret, stdout, stderr = fetch_pr_checks(pr_number, timeout=cli_timeout)
        if ret == 124:
            logger.warning("[Attempt %d/%d] gh pr checks timed out. Retrying in %ds...", attempt, max_attempts, interval)
        elif ret != 0 and not stdout:
            logger.warning("[Attempt %d/%d] gh pr checks returned error: %s", attempt, max_attempts, stderr)
        else:
            categories = parse_pr_checks_output(stdout)
            summary = evaluate_checks_summary(categories)
            counts = summary["counts"]
            logger.info(
                "[Attempt %d/%d] Status: %s | Passed: %d, Pending: %d, Blocked: %d, Failed: %d (Total: %d)",
                attempt,
                max_attempts,
                summary["status"],
                counts["passed"],
                counts["pending"],
                counts["blocked"],
                counts["failed"],
                counts["total"],
            )

            if summary["status"] == "SUCCESS":
                return {"final_status": "SUCCESS", "can_merge": True, "attempts": attempt, "categories": categories}
            if summary["status"] in ("FAILURE", "BLOCKED"):
                return {"final_status": summary["status"], "can_merge": False, "attempts": attempt, "categories": categories}

        if attempt < max_attempts:
            time.sleep(interval)

    return {"final_status": "TIMEOUT", "can_merge": False, "attempts": max_attempts, "categories": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PR CI status with finite timeout")
    parser.add_argument("--pr", type=int, required=True, help="PR number to monitor")
    parser.add_argument("--max-attempts", type=int, default=20, help="Max polling attempts (default: 20)")
    parser.add_argument("--interval", type=int, default=15, help="Interval between attempts in seconds (default: 15)")
    parser.add_argument("--cli-timeout", type=float, default=DEFAULT_CLI_TIMEOUT, help="Subprocess timeout in seconds (max 10s)")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    if args.cli_timeout > MAX_CLI_TIMEOUT:
        sys.stderr.write(f"Error: --cli-timeout must not exceed {MAX_CLI_TIMEOUT}s (got {args.cli_timeout}s)\n")
        return 1

    result = poll_pr_checks(
        pr_number=args.pr,
        max_attempts=args.max_attempts,
        interval=args.interval,
        cli_timeout=args.cli_timeout,
    )

    if args.json:
        # Convert Enum keys to string for JSON serialization
        json_obj = dict(result)
        if "categories" in json_obj and isinstance(json_obj["categories"], dict):
            json_obj["categories"] = {str(k.value if isinstance(k, CheckCategory) else k): v for k, v in json_obj["categories"].items()}
        print(json.dumps(json_obj, ensure_ascii=False, indent=2))
    else:
        status = result.get("final_status", "UNKNOWN")
        if status == "SUCCESS":
            print(f"\n🎉 PR #{args.pr} CI Checks PASSED! Ready to merge.")
        elif status == "BLOCKED":
            print(f"\n⚠️ PR #{args.pr} CI has BLOCKED/action_required checks. Please inspect with `gh run view <run-id>`.")
        elif status == "FAILURE":
            print(f"\n❌ PR #{args.pr} CI Checks FAILED.")
        else:
            print(f"\n⏱️ PR #{args.pr} CI Checks monitoring TIMED OUT.")

    return 0 if result.get("can_merge") else 1


if __name__ == "__main__":
    sys.exit(main())
