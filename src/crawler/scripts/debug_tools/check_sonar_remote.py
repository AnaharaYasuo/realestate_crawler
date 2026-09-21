#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonarCloud Remote Inspection Tool (check_sonar_remote.py)
Issue #299: Ensures finite timeout on all remote SonarCloud API calls to prevent hanging processes.
"""
import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env  # noqa: E402
setup_env.init_environment()

DEFAULT_TIMEOUT_SEC: float = 10.0
DEFAULT_PROJECT_KEY: str = "AnaharaYasuo_realestate_crawler"
SONARCLOUD_API_BASE: str = "https://sonarcloud.io/api"


class SonarTimeoutException(Exception):
    """Raised when SonarCloud API call exceeds the finite timeout limit."""
    pass


class SonarApiException(Exception):
    """Raised when SonarCloud API returns an error or invalid response."""
    pass


def _execute_api_get(url: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> Dict[str, Any]:
    """Execute HTTP GET with strict socket-level finite timeout."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RealEstateCrawler-SonarRemoteCheck/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)
    except (TimeoutError, socket.timeout) as exc:
        raise SonarTimeoutException(f"SonarCloud API request timed out after {timeout}s: {url}") from exc
    except urllib.error.HTTPError as exc:
        raise SonarApiException(f"SonarCloud API HTTP {exc.code} {exc.reason}: {url}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)) or "timed out" in str(exc.reason).lower():
            raise SonarTimeoutException(f"SonarCloud API request timed out after {timeout}s: {url}") from exc
        raise SonarApiException(f"Network error connecting to SonarCloud ({url}): {exc.reason}") from exc
    except Exception as exc:
        raise SonarApiException(f"Failed to parse SonarCloud response ({url}): {exc}") from exc


def fetch_quality_gate(
    project_key: str = DEFAULT_PROJECT_KEY,
    pr_number: Optional[int] = None,
    branch: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Fetch Quality Gate status for project, pull request, or branch."""
    params = {"projectKey": project_key}
    if pr_number is not None:
        params["pullRequest"] = str(pr_number)
    elif branch:
        params["branch"] = branch

    query_str = urllib.parse.urlencode(params)
    url = f"{SONARCLOUD_API_BASE}/qualitygates/project_status?{query_str}"
    data = _execute_api_get(url, timeout=timeout)
    return data.get("projectStatus", {})


def fetch_unresolved_issues(
    project_key: str = DEFAULT_PROJECT_KEY,
    pr_number: Optional[int] = None,
    branch: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch unresolved issues list and total count."""
    params = {"componentKeys": project_key, "resolved": "false"}
    if pr_number is not None:
        params["pullRequest"] = str(pr_number)
    elif branch:
        params["branch"] = branch

    query_str = urllib.parse.urlencode(params)
    url = f"{SONARCLOUD_API_BASE}/issues/search?{query_str}"
    data = _execute_api_get(url, timeout=timeout)
    issues = data.get("issues", [])
    total = data.get("total", len(issues))
    return issues, total


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SonarCloud Remote Inspection Tool with guaranteed finite timeout"
    )
    parser.add_argument("--pr", type=int, help="Target Pull Request number")
    parser.add_argument("--branch", type=str, help="Target Branch name")
    parser.add_argument("--project", type=str, default=DEFAULT_PROJECT_KEY, help="SonarCloud project key")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"Finite HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SEC}s)",
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--issues", action="store_true", help="Also list unresolved issues")
    args = parser.parse_args(argv)

    try:
        qg_status = fetch_quality_gate(
            project_key=args.project,
            pr_number=args.pr,
            branch=args.branch,
            timeout=args.timeout,
        )

        issues_data = []
        issues_total = 0
        if args.issues or qg_status.get("status") != "OK":
            issues_data, issues_total = fetch_unresolved_issues(
                project_key=args.project,
                pr_number=args.pr,
                branch=args.branch,
                timeout=args.timeout,
            )

        if args.json:
            out_obj = {
                "quality_gate": qg_status,
                "issues_total": issues_total,
                "issues": issues_data,
            }
            print(json.dumps(out_obj, ensure_ascii=False, indent=2))
            return 0 if qg_status.get("status") == "OK" else 1

        print("=" * 80)
        print(f" SonarCloud Remote Quality Gate Status (Timeout: {args.timeout}s)")
        print("=" * 80)
        status_str = qg_status.get("status", "UNKNOWN")
        target_info = f"PR #{args.pr}" if args.pr else (f"Branch '{args.branch}'" if args.branch else "Main/Master")
        print(f" Target: {target_info} ({args.project})")
        print(f" Quality Gate: {'PASS (OK)' if status_str == 'OK' else f'FAIL ({status_str})'}")

        conditions = qg_status.get("conditions", [])
        if conditions:
            print("\n Quality Gate Conditions:")
            for c in conditions:
                c_status = c.get("status")
                metric = c.get("metricKey")
                val = c.get("actualValue", "-")
                thresh = c.get("errorThreshold", "-")
                mark = "[OK]" if c_status == "OK" else "[ERROR]"
                print(f"   {mark} {metric}: {val} (threshold: {thresh})")

        if issues_total > 0:
            print(f"\n Unresolved Issues ({issues_total} total):")
            for iss in issues_data[:10]:
                rule = iss.get("rule")
                comp = iss.get("component")
                line = iss.get("line", "-")
                msg = iss.get("message")
                print(f"   - [{rule}] {comp}:{line} - {msg}")
            if issues_total > 10:
                print(f"   ... and {issues_total - 10} more issues.")

        print("=" * 80)
        return 0 if status_str == "OK" else 1

    except SonarTimeoutException as exc:
        sys.stderr.write(f"\n[TIMEOUT ERROR] {exc}\n")
        return 2
    except SonarApiException as exc:
        sys.stderr.write(f"\n[API ERROR] {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"\n[UNEXPECTED ERROR] {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
