#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Issue Acceptance Criteria Guardrail Scanner.

Validates that an associated GitHub Issue exists, defines Acceptance Criteria
checkboxes (- [ ]), and that all criteria have been verified and checked (- [x])
before allowing PR creation or merge.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple, Any



def extract_issue_number(branch_name: str, commit_msg: str = "") -> Optional[int]:
    """
    Extract GitHub issue number from branch name or commit message.

    Supports formats like:
      feature/219-sonar-guardrail -> 219
      fix/issue-34-parse-error    -> 34
      feat: add auth (#123)       -> 123
    """
    # 1. Check branch name pattern: feature/123-xxx or fix/123-xxx
    branch_match = re.search(r"(?:feature|fix|chore|refactor|issue)[/-](?:issue[-_#]?)?(\d+)", branch_name, re.IGNORECASE)
    if branch_match:
        return int(branch_match.group(1))

    # 2. Check generic number in branch
    generic_match = re.search(r"(?:^|[-/_])(\d+)(?:[-/_]|$)", branch_name)
    if generic_match:
        return int(generic_match.group(1))

    # 3. Check commit message
    if commit_msg:
        commit_match = re.search(r"(?:(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s+#|#|issue[ -]?#?)(\d+)", commit_msg, re.IGNORECASE)
        if commit_match:
            return int(commit_match.group(1))

    return None


def parse_acceptance_criteria(body: str) -> Tuple[List[str], List[str]]:
    """
    Parse markdown task list checkboxes from issue body.

    Returns:
      (checked_items, unchecked_items)
    """
    checked = []
    unchecked = []

    for line in body.splitlines():
        stripped = line.strip()
        # Match - [ ] or - [x] or * [ ] or * [x]
        m = re.match(r"^[-*]\s+\[([ xX])\]\s+(.*)$", stripped)
        if not m:
            continue
        status_char = m.group(1)
        item_text = m.group(2).strip()
        if status_char in ("x", "X"):
            checked.append(item_text)
        else:
            unchecked.append(item_text)

    return checked, unchecked


def _get_current_git_info() -> Tuple[str, str]:
    """Retrieve current git branch name and latest commit message."""
    branch = ""
    commit_msg = ""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            branch = res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            commit_msg = res.stdout.strip()
    except Exception:
        pass

    return branch, commit_msg


def _fetch_issue_via_api(issue_num: int) -> Optional[Dict[str, Any]]:
    """Fetch issue metadata directly via GitHub REST API as fallback."""
    url = f"https://api.github.com/repos/AnaharaYasuo/realestate_crawler/issues/{issue_num}"
    headers = {"User-Agent": "realestate-crawler-gate"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "number": data.get("number"),
                "title": data.get("title", ""),
                "body": data.get("body", "") or "",
                "state": data.get("state", ""),
            }
    except Exception:
        return None


def fetch_issue_data(issue_num: int) -> Optional[Dict[str, Any]]:
    """Fetch issue metadata from GitHub using gh CLI with API fallback."""
    try:
        res = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "number,title,body,state"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception:
        pass

    return _fetch_issue_via_api(issue_num)


def validate_issue_acceptance_criteria(issue_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate that the issue contains acceptance criteria and all are checked.

    Returns:
      (is_valid, summary_message, details_dict)
    """
    body = issue_data.get("body", "") or ""
    issue_num = issue_data.get("number")
    title = issue_data.get("title", "")

    checked, unchecked = parse_acceptance_criteria(body)
    total_criteria = len(checked) + len(unchecked)

    details = {
        "issue_number": issue_num,
        "title": title,
        "total_criteria": total_criteria,
        "checked_count": len(checked),
        "unchecked_count": len(unchecked),
        "checked_items": checked,
        "unchecked_items": unchecked,
    }

    if total_criteria == 0:
        msg = f"Issue #{issue_num} does not contain any Acceptance Criteria checkboxes (- [ ])."
        return False, msg, details

    if unchecked:
        msg = f"Issue #{issue_num} has {len(unchecked)} unchecked Acceptance Criteria out of {total_criteria}."
        return False, msg, details

    msg = f"All {total_criteria} Acceptance Criteria in Issue #{issue_num} are checked and verified."
    return True, msg, details


def _print_report(is_valid: bool, msg: str, details: Dict[str, Any], quiet: bool = False) -> None:
    """Print structured console report for acceptance criteria validation."""
    if quiet:
        return

    issue_num = details.get("issue_number")
    title = details.get("title", "")

    print("=" * 80)
    print(f" GitHub Issue Acceptance Criteria Guardrail: Issue #{issue_num}")
    print(f" Title: {title}")
    print("=" * 80)

    if is_valid:
        print(f"\n SUCCESS: {msg}")
        print(f" Completed criteria: {details.get('checked_count', 0)}/{details.get('total_criteria', 0)}")
        for item in details.get("checked_items", []):
            print(f"   [x] {item}")
        print("\n" + "=" * 80)
    else:
        print(f"\n FAILED: {msg}")
        unchecked = details.get("unchecked_items", [])
        if unchecked:
            print("\n Remaining Unchecked Criteria:")
            for item in unchecked:
                print(f"   [ ] {item}")
        print("\n Action required: Fulfill and check all criteria in the Issue before submitting PR.")
        print("=" * 80)


def main() -> int:
    """Entry point for check_issue_criteria CLI."""
    parser = argparse.ArgumentParser(description="Verify that GitHub Issue acceptance criteria are all checked.")
    parser.add_argument("--branch", type=str, help="Branch name to extract issue number from")
    parser.add_argument("--issue", type=int, help="Explicit GitHub Issue number")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose stdout")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    # Determine branch and commit info
    git_branch, git_commit = _get_current_git_info()
    target_branch = args.branch or git_branch

    # Determine issue number
    issue_num = args.issue or extract_issue_number(target_branch, git_commit)
    if not issue_num:
        err = {"error": "Could not identify GitHub Issue number from branch or arguments."}
        if args.json:
            print(json.dumps(err))
        elif not args.quiet:
            print("=" * 80)
            print(" FAILED: No associated GitHub Issue found.")
            print(f" Current branch: {target_branch}")
            print(" Naming convention: feature/<issue_num>-<topic> or fix/<issue_num>-<topic>")
            print("=" * 80)
        return 1

    issue_data = fetch_issue_data(issue_num)
    if not issue_data:
        err = {"error": f"Failed to retrieve Issue #{issue_num} from GitHub."}
        if args.json:
            print(json.dumps(err))
        elif not args.quiet:
            print(f" FAILED: Issue #{issue_num} was not found on GitHub or gh CLI failed.")
        return 1

    is_valid, msg, details = validate_issue_acceptance_criteria(issue_data)

    if args.json:
        output = {"valid": is_valid, "message": msg, **details}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print_report(is_valid, msg, details, quiet=args.quiet)

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
