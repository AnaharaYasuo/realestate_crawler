#!/usr/bin/env python3
"""Antigravity Lifecycle Hook Guard (PreToolUse).

Mechanically enforces:
1. Principle 1 (Strictly Headless): Denies launching GUI applications such as Docker Desktop.exe.
2. Principle 3 (Always Worktree): Denies editing repository files (src/, docs/, terraform/, .github/)
   directly in the main working tree outside .worktrees/.
3. Principle 6 (2-Stage Release): Denies direct `git push origin production`.
"""
import json
import re
import sys


def _is_protected_main_tree_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    return (
        "/.worktrees/" not in norm
        and "/brain/" not in norm
        and bool(re.search(r"/realestate_crawler/(src|docs|terraform|\.github|\.agents)/", norm))
    )


def _extract_created_branch_name(cmd: str) -> str | None:
    """Return newly created/renamed branch name if cmd creates or renames a git branch."""
    git_prefix = r"\bgit\s+(?:-C\s+\S+\s+)*"
    patterns = (
        rf"{git_prefix}checkout\s+(?:[^\s;&|]+\s+)*-[bB]\s+([A-Za-z0-9._/-]+)",
        rf"{git_prefix}switch\s+(?:[^\s;&|]+\s+)*(?:-[cC]|--create|--force-create)\s+([A-Za-z0-9._/-]+)",
        rf"{git_prefix}worktree\s+add\s+(?:[^\s;&|]+\s+)*-[bB]\s+([A-Za-z0-9._/-]+)",
        rf"{git_prefix}branch\s+(?:-[mM]|--move)\s+(?:[A-Za-z0-9._/-]+\s+)?([A-Za-z0-9._/-]+)",
        rf"{git_prefix}branch\s+(?!-)([A-Za-z0-9._/-]+)",
    )
    for pat in patterns:
        m = re.search(pat, cmd)
        if m:
            return m.group(1)
    return None


def _check_branch_creation_guard(cmd: str) -> dict | None:
    branch = _extract_created_branch_name(cmd)
    if branch and branch not in ("master", "production", "main", "HEAD") and not re.search(r"\d+", branch):
        return {
            "decision": "deny",
            "reason": (
                f"Principle 4 violation: Creating or renaming branch '{branch}' without a GitHub Issue number "
                "in the branch name is forbidden (e.g. feat/<issue_num>-<slug>)."
            ),
        }
    return None


def _check_issue_pr_and_push_guard(cmd: str) -> dict | None:
    branch_verdict = _check_branch_creation_guard(cmd)
    if branch_verdict is not None:
        return branch_verdict

    if re.search(r"\bgh\s+pr\s+create\b", cmd):
        is_release_pr = bool(re.search(r"(?:--base|-B)\s+['\"]?production\b", cmd))
        title_match = re.search(r"(?:--title|-t)\s+['\"]\[#(\d+)\]\s+", cmd)
        body_match = re.search(r"\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s+#(\d+)\b", cmd, re.IGNORECASE)
        same_issue = bool(title_match and body_match and title_match.group(1) == body_match.group(1))
        if not is_release_pr and not same_issue:
            return {
                "decision": "deny",
                "reason": "Principle 4 violation: Issue-less, untagged, or mismatched PR creation is forbidden. Prefix --title with '[#<IssueNumber>] ' and include matching 'Closes #<IssueNumber>' in --body.",
            }
        if not is_release_pr:
            try:
                diff_out = subprocess.check_output(
                    ["git", "diff", "--name-only", "origin/master...HEAD"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                changed = [line.strip() for line in diff_out.splitlines() if line.strip()]
                if changed and not any(re.match(r"^docs/[1-7]_", f) for f in changed):
                    return {
                        "decision": "deny",
                        "reason": "Principle 4 (SDD) violation: PR to master must include a 7-domain SSOT specification update (docs/1_... through docs/7_.../*.md).",
                    }
            except Exception:
                pass

    push_match = re.search(
        r"\bgit\s+(?:-C\s+\S+\s+)?push\s+(?:-[a-zA-Z-]+\s+)*origin\s+(?!--delete\b|-d\b|:)([A-Za-z0-9._/-]+)",
        cmd,
    )
    if push_match:
        branch = push_match.group(1)
        if branch not in ("master", "production", "HEAD") and not re.search(r"\d+", branch):
            return {
                "decision": "deny",
                "reason": f"Principle 4 violation: Pushing branch '{branch}' without a GitHub Issue number in the branch name is forbidden.",
            }
    return None


def _is_test_file_path(path: str) -> bool:
    norm = path.replace("\\", "/")
    return bool(re.search(r"/tests/(?:.+/)?test_[^/]+\.py$", norm))


def _check_test_tampering(path: str, args: dict) -> dict | None:
    """Prevent AI agents from weakening or skipping existing tests (Reward Hacking)."""
    if not _is_test_file_path(path):
        return None
    target = str(args.get("Target") or "")
    replacement = str(args.get("Replacement") or args.get("Content") or "")
    if not replacement:
        return None

    skip_pattern = re.compile(r"@pytest\.mark\.skip|pytest\.skip\(|@unittest\.skip")
    if skip_pattern.search(replacement) and not skip_pattern.search(target):
        return {
            "decision": "deny",
            "reason": "Test tampering guard: Adding skip/skipif to test files is forbidden.",
        }
    if re.search(r"^\s*#\s*assert\b", replacement, re.MULTILINE) and re.search(
        r"^\s*assert\b", target, re.MULTILINE
    ):
        return {
            "decision": "deny",
            "reason": "Test tampering guard: Commenting out assertions in test files is forbidden.",
        }
    if re.search(r"^\s*assert\s+True\b", replacement, re.MULTILINE) and not re.search(
        r"^\s*assert\s+True\b", target, re.MULTILINE
    ):
        return {
            "decision": "deny",
            "reason": "Test tampering guard: Replacing assertions with trivial 'assert True' is forbidden.",
        }
    return None


def _evaluate_run_command(cmd: str) -> dict | None:
    is_search_cmd = bool(re.search(r"^\s*(rg|grep|select-string|git\s+grep)\b", cmd, re.IGNORECASE))
    if re.search(r"Docker\s*Desktop\.exe", cmd, re.IGNORECASE) and not is_search_cmd:
        return {
            "decision": "deny",
            "reason": "Principle 1 violation: Launching GUI Docker Desktop.exe is strictly forbidden. Use headless daemon/CLI.",
        }
    if re.search(r"git\s+push\s+origin\s+production\b", cmd):
        return {
            "decision": "deny",
            "reason": "Principle 6 violation: Direct push to 'production' is forbidden. Use a release PR from 'master' to 'production'.",
        }
    if re.search(r"gcloud(?:\.cmd)?[\"']?\s+compute\s+instances\s+stop\b.*proxysql", cmd, re.IGNORECASE) and not is_search_cmd:
        return {
            "decision": "deny",
            "reason": "ProxySQL protection: Direct 'gcloud compute instances stop ... proxysql' is forbidden. Stop all DB-connected processes first and verify zero active DB connections before stopping ProxySQL.",
        }
    if re.search(r"gh\s+pr\s+checks\b.*--watch\b", cmd):
        return {
            "decision": "deny",
            "reason": "Infinite '--watch' on gh pr checks is forbidden. Use check_pr_ci_status.py with finite polling.",
        }
    issue_verdict = _check_issue_pr_and_push_guard(cmd)
    if issue_verdict is not None:
        return issue_verdict
    if re.search(r"(>|Set-Content|Out-File|Add-Content)", cmd, re.IGNORECASE) and _is_protected_main_tree_path(cmd):
        return {
            "decision": "deny",
            "reason": "Principle 3 violation: Direct file write on the main working tree via shell command is forbidden.",
        }
    return None


def evaluate_tool_call(payload: dict) -> dict:
    tool_call = payload.get("toolCall") or {}
    tool_name = (tool_call.get("name") or "").lower()
    args = tool_call.get("args") or {}

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or "")
        verdict = _evaluate_run_command(cmd)
        if verdict is not None:
            return verdict

    elif tool_name in (
        "edit_file",
        "write_file",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    ):
        raw_path = args.get("Path") or args.get("TargetFile") or ""
        if _is_protected_main_tree_path(str(raw_path)):
            return {
                "decision": "deny",
                "reason": "Principle 3 violation: Direct file modification on the main working tree is forbidden. Edit inside '.worktrees/<branch-name>/'.",
            }
        tamper_verdict = _check_test_tampering(str(raw_path), args)
        if tamper_verdict is not None:
            return tamper_verdict

    return {"decision": "allow"}


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        result = evaluate_tool_call(payload)
    except Exception:  # noqa: BLE001
        result = {"decision": "allow"}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
