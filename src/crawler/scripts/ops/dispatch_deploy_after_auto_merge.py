"""Wait for the master -> production release PR to merge and dispatch the production deploy.

Pushes made by GITHUB_TOKEN (auto-merge enabled by auto-release-pr.yml) do not trigger
deploy-production.yml, so the deploy is dispatched explicitly in that case only.
Merges by a human token trigger the push event themselves and must not be dispatched again.
Uses only the standard library so it runs on a bare GitHub Actions runner.
"""
import argparse
import json
import subprocess
import sys
import time

GH_TIMEOUT_SEC = 10
DEPLOY_WORKFLOW = "deploy-production.yml"
PRODUCTION_BRANCH = "production"
AUTO_MERGE_ACTORS = frozenset({"app/github-actions", "github-actions"})

DISPATCH = "dispatch"
DISPATCH_FAILED = "dispatch_failed"
SKIP_HUMAN_MERGE = "skip_human_merge"
SKIP_CLOSED = "skip_closed"
TIMED_OUT = "timed_out"
WAIT = "wait"


def run_gh(args):
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT_SEC, check=False
    )
    return proc.returncode, proc.stdout


def decide_action(state, merged_by_login):
    if state == "MERGED":
        return DISPATCH if merged_by_login in AUTO_MERGE_ACTORS else SKIP_HUMAN_MERGE
    if state == "CLOSED":
        return SKIP_CLOSED
    return WAIT


def find_release_pr(gh=run_gh):
    rc, out = gh(
        ["pr", "list", "--base", PRODUCTION_BRANCH, "--head", "master", "--state", "open",
         "--json", "number"]
    )
    if rc != 0 or not out.strip():
        return None
    prs = json.loads(out)
    return str(prs[0]["number"]) if prs else None


def _poll_action(pr_number, gh):
    try:
        rc, out = gh(["pr", "view", pr_number, "--json", "state,mergedBy"])
        if rc != 0:
            return WAIT
        data = json.loads(out)
    except (subprocess.TimeoutExpired, ValueError) as exc:
        print(f"::notice::Transient error while polling PR #{pr_number}: {exc}")
        return WAIT
    merged_by = (data.get("mergedBy") or {}).get("login")
    return decide_action(data.get("state"), merged_by)


def _dispatch(gh):
    rc, _ = gh(["workflow", "run", DEPLOY_WORKFLOW, "--ref", PRODUCTION_BRANCH])
    return DISPATCH if rc == 0 else DISPATCH_FAILED


def wait_and_dispatch(pr_number, timeout_sec, interval_sec, run_gh=run_gh, sleep=time.sleep,
                      clock=time.monotonic):
    deadline = clock() + timeout_sec
    while True:
        action = _poll_action(pr_number, run_gh)
        if action == DISPATCH:
            return _dispatch(run_gh)
        if action != WAIT:
            return action
        if clock() + interval_sec > deadline:
            return TIMED_OUT
        sleep(interval_sec)


def exit_code_for(result):
    return 1 if result == DISPATCH_FAILED else 0


def main(argv=None, run_gh=run_gh):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--interval-sec", type=int, default=30)
    args = parser.parse_args(argv)

    pr_number = find_release_pr(run_gh)
    if pr_number is None:
        print("No open master -> production release PR; nothing to wait for.")
        return 0

    result = wait_and_dispatch(pr_number, args.timeout_sec, args.interval_sec, run_gh=run_gh)
    messages = {
        DISPATCH: f"PR #{pr_number} was auto-merged by github-actions; dispatched {DEPLOY_WORKFLOW}.",
        DISPATCH_FAILED: f"::error::Failed to dispatch {DEPLOY_WORKFLOW} after PR #{pr_number} merged.",
        SKIP_HUMAN_MERGE: f"PR #{pr_number} was merged by a user token; push trigger deploys it.",
        SKIP_CLOSED: f"PR #{pr_number} was closed without merge; no deploy.",
        TIMED_OUT: f"::warning::PR #{pr_number} not merged within {args.timeout_sec}s; no deploy dispatched.",
    }
    print(messages[result])
    return exit_code_for(result)


if __name__ == "__main__":
    sys.exit(main())
