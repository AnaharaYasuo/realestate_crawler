#!/usr/bin/env python3
"""
PR CI Status Inspector and Finite-Timeout Monitor (check_pr_ci_status.py)

Issue #602: Enforces finite timeouts and non-blocking polling on GitHub Actions CI checks,
banning unlimited `--watch` commands that hang on action_required or queued jobs.
"""
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from enum import Enum
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_pr_ci_status")

DEFAULT_CLI_TIMEOUT: float = 10.0
MAX_CLI_TIMEOUT: float = 10.0
MAX_CONSECUTIVE_TIMEOUTS: int = 3
DEFAULT_REPO: str = "AnaharaYasuo/realestate_crawler"


class CheckCategory(str, Enum):
    PASSED = "passed"
    PENDING = "pending"
    FAILED = "failed"
    BLOCKED = "blocked"


def classify_check_status(raw_status: str) -> CheckCategory:
    """Classify GitHub checks status into four main categories."""
    status = (raw_status or "").strip().lower()
    if not status:
        return CheckCategory.FAILED
    if status in ("pass", "success", "skipping", "skipped", "neutral"):
        return CheckCategory.PASSED
    if status in ("pending", "in_progress", "queued"):
        return CheckCategory.PENDING
    if status in ("action_required", "cancelled", "stalled"):
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

    # Precedence: FAILED > BLOCKED > PENDING > SUCCESS
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


def _fetch_pr_checks_via_api(
    pr_number: int,
    repo: str = DEFAULT_REPO,
    timeout: float = DEFAULT_CLI_TIMEOUT,
) -> tuple[int, str, str]:
    """Fallback: Fetch PR check runs and combined commit status from GitHub REST API."""
    bounded_timeout = min(timeout, MAX_CLI_TIMEOUT)
    headers = {"User-Agent": "realestate-crawler-ci-check", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=bounded_timeout) as resp:
            pr_data = json.loads(resp.read().decode("utf-8"))
            head_sha = pr_data.get("head", {}).get("sha", "")
        if not head_sha:
            return 1, "", "Could not resolve head SHA from PR metadata"

        lines = []

        # 1. Fetch check-runs (paginated, sorted by ID so latest run wins per name)
        latest_runs: dict[str, dict[str, Any]] = {}
        page = 1
        while True:
            check_runs_url = f"https://api.github.com/repos/{repo}/commits/{head_sha}/check-runs?per_page=100&page={page}"
            req_runs = urllib.request.Request(check_runs_url, headers=headers)
            with urllib.request.urlopen(req_runs, timeout=bounded_timeout) as resp_runs:
                runs_data = json.loads(resp_runs.read().decode("utf-8"))
            runs_list = runs_data.get("check_runs", [])
            for cr in sorted(runs_list, key=lambda x: x.get("id", 0)):
                name = cr.get("name", "unknown")
                # Keep latest check-run by ID
                if name not in latest_runs or cr.get("id", 0) > latest_runs[name].get("id", 0):
                    latest_runs[name] = cr
            if len(runs_list) < 100:
                break
            page += 1

        for name, cr in latest_runs.items():
            status = cr.get("status", "")
            conclusion = cr.get("conclusion", "")
            final_status = conclusion if status == "completed" else status
            html_url = cr.get("html_url", "")
            lines.append(f"{name}\t{final_status}\t0s\t{html_url}")

        # 2. Fetch combined commit statuses (e.g. review-gate, sonar, etc.)
        status_url = f"https://api.github.com/repos/{repo}/commits/{head_sha}/status"
        req_status = urllib.request.Request(status_url, headers=headers)
        with urllib.request.urlopen(req_status, timeout=bounded_timeout) as resp_status:
            status_data = json.loads(resp_status.read().decode("utf-8"))
        latest_statuses: dict[str, dict[str, Any]] = {}
        for st in status_data.get("statuses", []):
            ctx_name = st.get("context", "unknown")
            if ctx_name not in latest_statuses or st.get("id", 0) > latest_statuses[ctx_name].get("id", 0):
                latest_statuses[ctx_name] = st
        for ctx_name, st in latest_statuses.items():
            state = st.get("state", "")
            target_url = st.get("target_url", "")
            lines.append(f"{ctx_name}\t{state}\t0s\t{target_url}")

        return 0, "\n".join(lines), ""
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            return 2, "", f"Permanent HTTP {exc.code} error: {exc.reason}"
        return 1, "", f"API HTTP error {exc.code}: {exc.reason}"
    except (TimeoutError, urllib.error.URLError) as exc:
        if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
            return 124, "", f"API check timed out after {bounded_timeout}s"
        return 1, "", f"API network error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", f"API check failed: {exc}"


def fetch_pr_checks(
    pr_number: int,
    repo: str = DEFAULT_REPO,
    timeout: float = DEFAULT_CLI_TIMEOUT,
) -> tuple[int, str, str]:
    """Execute `gh pr checks <PR_NUM>` with finite timeout limit (max 10s), with REST API fallback."""
    bounded_timeout = min(timeout, MAX_CLI_TIMEOUT)
    try:
        res = subprocess.run(
            ["gh", "pr", "checks", str(pr_number), "--repo", repo],
            capture_output=True,
            text=True,
            timeout=bounded_timeout,
            check=False,
        )
        if res.returncode == 0 or res.stdout.strip():
            return res.returncode, res.stdout, res.stderr
        logger.debug("gh command failed with empty stdout: %s (falling back to REST API)", res.stderr)
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {bounded_timeout}s"
    except FileNotFoundError:
        # gh CLI not installed (e.g. inside docker container) -> fallback to REST API
        pass
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)

    return _fetch_pr_checks_via_api(pr_number, repo=repo, timeout=bounded_timeout)


def poll_pr_checks(
    pr_number: int,
    repo: str = DEFAULT_REPO,
    max_attempts: int = 20,
    interval: int = 15,
    cli_timeout: float = DEFAULT_CLI_TIMEOUT,
) -> dict[str, Any]:
    """Poll PR CI checks with finite timeouts and intervals."""
    logger.info(
        "Starting finite-timeout CI monitoring for PR #%d (repo=%s, max_attempts=%d, interval=%ds, timeout=%.1fs)",
        pr_number,
        repo,
        max_attempts,
        interval,
        cli_timeout,
    )

    empty_successes = 0
    consecutive_timeouts = 0
    retrieval_errors: list[str] = []

    for attempt in range(1, max_attempts + 1):
        ret, stdout, stderr = fetch_pr_checks(pr_number, repo=repo, timeout=cli_timeout)
        if ret == 2:
            # Permanent HTTP error (e.g. 401 Unauthorized, 403 Forbidden, 404 Not Found)
            err_msg = stderr or "Permanent HTTP failure"
            logger.error("[Attempt %d/%d] Permanent retrieval error encountered: %s", attempt, max_attempts, err_msg)
            return {
                "final_status": "RETRIEVAL_ERROR",
                "can_merge": False,
                "attempts": attempt,
                "categories": {},
                "error": err_msg,
            }
        if ret == 124:
            consecutive_timeouts += 1
            err_msg = stderr or "gh pr checks timed out"
            retrieval_errors.append(err_msg)
            logger.warning("[Attempt %d/%d] gh pr checks timed out (%d consecutive). Retrying in %ds...", attempt, max_attempts, consecutive_timeouts, interval)
            if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                logger.error("Fast-fail circuit breaker triggered: %d consecutive timeouts encountered.", consecutive_timeouts)
                return {
                    "final_status": "RETRIEVAL_ERROR",
                    "can_merge": False,
                    "attempts": attempt,
                    "categories": {},
                    "error": f"Circuit breaker: {consecutive_timeouts} consecutive timeouts ({err_msg})",
                }
        elif ret != 0 and not stdout:
            consecutive_timeouts = 0
            err_msg = stderr or f"gh pr checks failed with exit code {ret}"
            retrieval_errors.append(err_msg)
            logger.warning("[Attempt %d/%d] gh pr checks returned error: %s", attempt, max_attempts, stderr)
        else:
            consecutive_timeouts = 0
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
            if summary["status"] == "NO_CHECKS":
                empty_successes += 1

        if attempt < max_attempts:
            time.sleep(interval)

    if max_attempts > 0 and empty_successes == max_attempts:
        return {"final_status": "NO_CHECKS", "can_merge": False, "attempts": max_attempts, "categories": {}}
    if max_attempts > 0 and len(retrieval_errors) == max_attempts:
        return {
            "final_status": "RETRIEVAL_ERROR",
            "can_merge": False,
            "attempts": max_attempts,
            "categories": {},
            "error": retrieval_errors[-1],
        }

    return {"final_status": "TIMEOUT", "can_merge": False, "attempts": max_attempts, "categories": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PR CI status with finite timeout")
    parser.add_argument("--pr", type=int, required=True, help="PR number to monitor")
    parser.add_argument(
        "--repo",
        type=str,
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO),
        help=f"Target repo owner/name (default: {DEFAULT_REPO})",
    )
    parser.add_argument("--max-attempts", type=int, default=20, help="Max polling attempts (default: 20)")
    parser.add_argument("--interval", type=int, default=15, help="Interval between attempts in seconds (default: 15)")
    parser.add_argument("--cli-timeout", type=float, default=DEFAULT_CLI_TIMEOUT, help="Subprocess timeout in seconds (max 10s)")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    if args.max_attempts < 1:
        sys.stderr.write(f"Error: --max-attempts must be at least 1 (got {args.max_attempts})\n")
        return 1

    if args.interval < 0:
        sys.stderr.write(f"Error: --interval must be non-negative (got {args.interval})\n")
        return 1

    if args.cli_timeout <= 0 or args.cli_timeout > MAX_CLI_TIMEOUT:
        sys.stderr.write(f"Error: --cli-timeout must be > 0 and <= {MAX_CLI_TIMEOUT}s (got {args.cli_timeout}s)\n")
        return 1

    result = poll_pr_checks(
        pr_number=args.pr,
        repo=args.repo,
        max_attempts=args.max_attempts,
        interval=args.interval,
        cli_timeout=args.cli_timeout,
    )

    if args.json:
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
        elif status == "NO_CHECKS":
            print(f"\nℹ️ PR #{args.pr} has no CI checks registered.")
        elif status == "RETRIEVAL_ERROR":
            print(f"\n🚫 PR #{args.pr} CI checks retrieval failed: {result.get('error')}")
        else:
            print(f"\n⏱️ PR #{args.pr} CI Checks monitoring TIMED OUT.")

    return 0 if result.get("can_merge") else 1


if __name__ == "__main__":
    sys.exit(main())
