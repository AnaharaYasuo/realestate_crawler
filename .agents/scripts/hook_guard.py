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


def evaluate_tool_call(payload: dict) -> dict:
    tool_call = payload.get("toolCall") or {}
    tool_name = (tool_call.get("name") or "").lower()
    args = tool_call.get("args") or {}

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or "")
        if re.search(r"Docker\s*Desktop\.exe", cmd, re.IGNORECASE):
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

    elif tool_name in ("edit_file", "write_file"):
        path = str(args.get("Path") or "").replace("\\", "/")
        # Allow writing to brain/artifact/scratch directories or inside .worktrees/
        if "/.worktrees/" not in path and "/brain/" not in path:
            if re.search(r"/realestate_crawler/(src|docs|terraform|\.github|\.agents)/", path):
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
    except Exception:
        result = {"decision": "allow"}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
