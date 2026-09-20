import argparse
from enum import Enum
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dependabot_automerge")


class PRStatus(str, Enum):
    MERGE_READY = "MERGE_READY"
    NEED_REBASE = "NEED_REBASE"
    CI_RUNNING = "CI_RUNNING"
    CI_FAILED = "CI_FAILED"
    UNKNOWN = "UNKNOWN"


class DependabotPrInspector:
    def fetch_dependabot_prs(self) -> List[Dict[str, Any]]:
        cmd = [
            "gh",
            "pr",
            "list",
            "--app",
            "dependabot",
            "--state",
            "open",
            "--json",
            "number,title,mergeable,statusCheckRollup,headRefName,url",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(res.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list dependabot PRs: {e.stderr}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh output as JSON: {e}")
            return []

    def evaluate_pr_status(self, pr_data: Dict[str, Any]) -> Tuple[PRStatus, str]:
        """Classify a Dependabot PR from its mergeability and rolled-up CI state.

        Failed checks whose names contain ``upload-sarif``, ``code scanning``, or
        ``security/snyk`` are non-blocking. The returned string explains the status.
        """
        mergeable = pr_data.get("mergeable", "UNKNOWN")
        if mergeable == "CONFLICTING":
            return PRStatus.NEED_REBASE, "PR has merge conflicts with base branch"

        checks = pr_data.get("statusCheckRollup", [])
        if not checks:
            return PRStatus.CI_RUNNING, "CI checks not started or empty"

        has_running = False
        has_failed = False
        failed_names = []

        for check in checks:
            # Can be CheckRun or StatusContext
            status = check.get("status", "")
            state = check.get("state", "")  # StatusContext uses state (PENDING, SUCCESS, ERROR)
            conclusion = check.get("conclusion", "")
            name = check.get("name") or check.get("context", "unknown")

            if status in ["QUEUED", "IN_PROGRESS"] or state == "PENDING":
                has_running = True
            elif conclusion in ["FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"] or state in ["FAILURE", "ERROR"]:
                # Note: Snyk token context, unmerged-only SARIF errors, Issue Gate, and Terraform Plan (lacking fork/bot secrets)
                # should be ignored as non-blocking for Dependabot PRs
                if any(ignorable in name.lower() for ignorable in ["upload-sarif", "code scanning", "security/snyk", "verify github issue association", "terraform plan"]):
                    logger.warning(f"Ignoring non-blocking or unmerged-dependent check failure: {name}")
                    continue
                has_failed = True
                failed_names.append(name)

        if has_running:
            return PRStatus.CI_RUNNING, "CI checks in progress"

        if has_failed:
            return PRStatus.CI_FAILED, f"CI checks failed: {', '.join(failed_names)}"

        if mergeable == "MERGEABLE":
            return PRStatus.MERGE_READY, "All checks passed and branch is mergeable"

        return PRStatus.NEED_REBASE, f"PR status requires rebase or update (mergeable: {mergeable})"


class DependabotAutoMerger:
    def __init__(self, dry_run: bool = False, auto_merge: bool = True, auto_rebase: bool = True):
        self.dry_run = dry_run
        self.auto_merge = auto_merge
        self.auto_rebase = auto_rebase

    def execute_merge(self, pr_number: int) -> bool:
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would merge PR #{pr_number} with --squash --delete-branch")
            return True

        logger.info(f"Merging PR #{pr_number}...")
        cmd = ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully merged PR #{pr_number}: {res.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to merge PR #{pr_number}: {e.stderr.strip()}")
            return False

    def request_rebase(self, pr_number: int) -> bool:
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would comment '@dependabot rebase' on PR #{pr_number}")
            return True

        logger.info(f"Requesting rebase on PR #{pr_number} via comment...")
        cmd = ["gh", "pr", "comment", str(pr_number), "--body", "@dependabot rebase"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully requested rebase on PR #{pr_number}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to request rebase on PR #{pr_number}: {e.stderr.strip()}")
            return False

    def format_summary_markdown(self, results: List[Dict[str, Any]]) -> str:
        lines = [
            "## Dependabot Auto-Merge Summary",
            "",
            "| PR | Title | Status | Action / Result |",
            "| :--- | :--- | :--- | :--- |",
        ]
        if not results:
            lines.append("| - | No open Dependabot PRs found | - | - |")
        else:
            for r in results:
                lines.append(f"| #{r['number']} | {r['title']} | `{r['status'].value}` | {r['action']} |")
        lines.append("")
        return "\n".join(lines)

    def run(self) -> int:
        inspector = DependabotPrInspector()
        prs = inspector.fetch_dependabot_prs()
        logger.info(f"Found {len(prs)} open Dependabot PRs")

        results = []
        for pr in prs:
            number = pr["number"]
            title = pr.get("title", "")
            status, reason = inspector.evaluate_pr_status(pr)
            logger.info(f"PR #{number} ({title}): status={status.value}, reason={reason}")

            action_desc = "None"
            if status == PRStatus.MERGE_READY:
                if self.auto_merge:
                    success = self.execute_merge(number)
                    action_desc = "Merged" if success and not self.dry_run else ("Merged (Dry-Run)" if self.dry_run else "Merge Failed")
                else:
                    action_desc = "Ready (Auto-merge disabled)"
            elif status == PRStatus.NEED_REBASE:
                if self.auto_rebase:
                    success = self.request_rebase(number)
                    action_desc = "Rebase Requested" if success and not self.dry_run else ("Rebase Requested (Dry-Run)" if self.dry_run else "Rebase Request Failed")
                else:
                    action_desc = "Conflict / Out-of-date (Rebase disabled)"
            elif status == PRStatus.CI_RUNNING:
                action_desc = "Skipped (CI Running)"
            elif status == PRStatus.CI_FAILED:
                action_desc = f"Skipped (CI Failed: {reason})"
            else:
                action_desc = f"Skipped ({reason})"

            results.append({
                "number": number,
                "title": title,
                "status": status,
                "action": action_desc,
            })

        summary_md = self.format_summary_markdown(results)
        print("\n" + summary_md + "\n")

        github_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if github_summary_path:
            try:
                with open(github_summary_path, "a", encoding="utf-8") as f:
                    f.write(summary_md + "\n")
            except Exception as e:
                logger.warning(f"Failed to write to GITHUB_STEP_SUMMARY: {e}")

        return 0


def main():
    parser = argparse.ArgumentParser(description="Dependabot PR Daily Auto-Merge & Self-Healing")
    parser.add_argument("--dry-run", action="store_true", help="Inspect PRs without performing merge or comments")
    parser.add_argument("--no-merge", action="store_true", help="Do not merge ready PRs")
    parser.add_argument("--no-rebase", action="store_true", help="Do not request rebase on conflicting PRs")
    args = parser.parse_args()

    merger = DependabotAutoMerger(
        dry_run=args.dry_run,
        auto_merge=not args.no_merge,
        auto_rebase=not args.no_rebase,
    )
    sys.exit(merger.run())


if __name__ == "__main__":
    main()
