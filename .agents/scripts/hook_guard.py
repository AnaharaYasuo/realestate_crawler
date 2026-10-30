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
    if re.search(r"gh\s+pr\s+checks\b.*--watch\b", cmd):
        return {
            "decision": "deny",
            "reason": "Infinite '--watch' on gh pr checks is forbidden. Use check_pr_ci_status.py with finite polling.",
        }
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
