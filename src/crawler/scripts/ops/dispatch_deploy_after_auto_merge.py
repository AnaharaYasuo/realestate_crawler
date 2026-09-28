"""Ensure production is deployed after the master -> production release PR merges.

Pushes made by GITHUB_TOKEN (auto-merge enabled by auto-release-pr.yml) do not trigger
deploy-production.yml, so the deploy is dispatched whenever the production head still has no
deploy run after a grace period. A merge by a user token creates its own push run and is not
dispatched. Uses only the standard library so it runs on a bare GitHub Actions runner.
"""
import argparse
import json
import subprocess
import sys
import time

GH_TIMEOUT_SEC = 10
LOOKUP_ATTEMPTS = 3
LOOKUP_RETRY_SEC = 5
DEPLOY_WORKFLOW = "deploy-production.yml"
PRODUCTION_BRANCH = "production"

MERGED = "merged"
WAIT = "wait"
DISPATCH = "dispatch"
DISPATCH_FAILED = "dispatch_failed"
ALREADY_DEPLOYED = "already_deployed"
SKIP_CLOSED = "skip_closed"
TIMED_OUT = "timed_out"
POLL_FAILED = "poll_failed"
LOOKUP_FAILED = "lookup_failed"

FAILURE_RESULTS = frozenset({DISPATCH_FAILED, POLL_FAILED, LOOKUP_FAILED})


def run_gh(args):
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT_SEC, check=False
    )
    return proc.returncode, proc.stdout


def decide_action(state):
    if state == "MERGED":
        return MERGED
    if state == "CLOSED":
        return SKIP_CLOSED
    return WAIT


def has_deploy_run(gh, sha):
    """True if a non-cancelled deploy run exists for sha, None if it cannot be determined."""
    try:
        rc, out = gh(["run", "list", "--workflow", DEPLOY_WORKFLOW, "--commit", sha,
                      "--json", "status,conclusion"])
        if rc != 0:
            return None
        runs = json.loads(out or "[]")
    except (subprocess.TimeoutExpired, ValueError):
        return None
    return any(run.get("conclusion") != "cancelled" for run in runs)


def lookup_deploy_run(gh, sha, sleep=time.sleep):
    """has_deploy_run with bounded retries; None means the lookup kept failing."""
    for attempt in range(LOOKUP_ATTEMPTS):
        found = has_deploy_run(gh, sha)
        if found is not None:
            return found
        if attempt < LOOKUP_ATTEMPTS - 1:
            sleep(LOOKUP_RETRY_SEC)
    return None


def get_production_head(gh):
    try:
        rc, out = gh(["api", f"repos/{{owner}}/{{repo}}/branches/{PRODUCTION_BRANCH}",
                      "--jq", ".commit.sha"])
    except subprocess.TimeoutExpired:
        return None
    sha = out.strip()
    return sha if rc == 0 and sha else None


def dispatch_deploy(gh):
    try:
        rc, _ = gh(["workflow", "run", DEPLOY_WORKFLOW, "--ref", PRODUCTION_BRANCH])
    except subprocess.TimeoutExpired:
        return DISPATCH_FAILED
    return DISPATCH if rc == 0 else DISPATCH_FAILED


def _head_deployed(gh, sleep):
    """Whether the current production head has a deploy run; None on lookup failure."""
    head = get_production_head(gh)
    if head is None:
        return None
    return lookup_deploy_run(gh, head, sleep)


def ensure_production_deployed(gh, grace_sec, sleep=time.sleep):
    """Dispatch only if the current production head still has no deploy run after the grace period.

    The head is re-read after waiting so the check always targets what dispatch would deploy.
    """
    found = _head_deployed(gh, sleep)
    if found is None:
        return LOOKUP_FAILED
    if found:
        return ALREADY_DEPLOYED
    sleep(grace_sec)
    found = _head_deployed(gh, sleep)
    if found is None:
        return LOOKUP_FAILED
    return ALREADY_DEPLOYED if found else dispatch_deploy(gh)


def find_release_pr(gh):
    """Open master -> production PR number, "" when none is open, None when the lookup failed."""
    try:
        rc, out = gh(["pr", "list", "--base", PRODUCTION_BRANCH, "--head", "master",
                      "--state", "open", "--json", "number"])
        if rc != 0:
            return None
        prs = json.loads(out or "[]")
    except (subprocess.TimeoutExpired, ValueError):
        return None
    return str(prs[0]["number"]) if prs else ""


def _poll(pr_number, gh):
    """Return (action, merge_sha), or None when the poll itself failed."""
    try:
        rc, out = gh(["pr", "view", pr_number, "--json", "state,mergeCommit"])
        if rc != 0:
            return None
        data = json.loads(out)
    except (subprocess.TimeoutExpired, ValueError) as exc:
        print(f"::notice::Transient error while polling PR #{pr_number}: {exc}")
        return None
    merge_sha = (data.get("mergeCommit") or {}).get("oid")
    return decide_action(data.get("state")), merge_sha


def wait_for_merge(pr_number, timeout_sec, interval_sec, run_gh=run_gh, sleep=time.sleep,
                   clock=time.monotonic, max_errors=10):
    deadline = clock() + timeout_sec
    errors = 0
    while True:
        polled = _poll(pr_number, run_gh)
        if polled is None:
            errors += 1
            if errors >= max_errors:
                return POLL_FAILED, None
        else:
            errors = 0
            if polled[0] != WAIT:
                return polled
        if clock() + interval_sec > deadline:
            return TIMED_OUT, None
        sleep(interval_sec)


def exit_code_for(result):
    return 1 if result in FAILURE_RESULTS else 0


def annotation_for(result):
    if result in FAILURE_RESULTS:
        return "::error::"
    if result == TIMED_OUT:
        return "::warning::"
    return ""


def main(argv=None, run_gh=run_gh, sleep=time.sleep, clock=time.monotonic):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", default="")
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--interval-sec", type=int, default=30)
    parser.add_argument("--grace-sec", type=int, default=90)
    parser.add_argument("--max-consecutive-errors", type=int, default=10)
    args = parser.parse_args(argv)

    reconciled = ensure_production_deployed(run_gh, args.grace_sec, sleep=sleep)
    print(f"{annotation_for(reconciled)}Startup reconcile of production head: {reconciled}")
    if reconciled in FAILURE_RESULTS:
        return exit_code_for(reconciled)

    # An empty number (PR step failed) must not drop a merge a cancelled older waiter was watching.
    pr_number = args.pr_number.strip() or find_release_pr(run_gh)
    if pr_number is None:
        print(f"{annotation_for(LOOKUP_FAILED)}Could not look up the open release PR.")
        return exit_code_for(LOOKUP_FAILED)
    if not pr_number:
        print("No open master -> production release PR to wait for.")
        return 0

    action, merge_sha = wait_for_merge(pr_number, args.timeout_sec, args.interval_sec,
                                       run_gh=run_gh, sleep=sleep, clock=clock,
                                       max_errors=args.max_consecutive_errors)
    if action == MERGED:
        print(f"Release PR #{pr_number} merged as {merge_sha}; ensuring production is deployed.")
        action = ensure_production_deployed(run_gh, args.grace_sec, sleep=sleep)
    print(f"{annotation_for(action)}Release PR #{pr_number}: {action}")
    return exit_code_for(action)


if __name__ == "__main__":
    sys.exit(main())
