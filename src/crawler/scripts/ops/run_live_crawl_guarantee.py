"""
Run live crawl-guarantee tests with environment-aware parallelism.

Local: static HTML jobs with capped xdist; Playwright companies serial.
CI (GITHUB_ACTIONS): static with -n auto; Playwright companies serial.

Static bucket runs overlapped with the Playwright chain so wall-clock can stay
≤300s (design: static ∥ (mizuho → (sekisui ∥ athome)); mizuho sitemap first,
then at most two Chromium companies).

Usage (inside container):
  python src/crawler/scripts/ops/run_live_crawl_guarantee.py
  CRAWL_GUARANTEE_SITES=sumifu python .../run_live_crawl_guarantee.py
  CRAWL_LIVE_PARALLEL_MODE=ci python .../run_live_crawl_guarantee.py
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env

        setup_env.init_environment()
        break
    _cur = _parent

_crawler_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

from package.utils.crawl_jobs import jobs_from_env
from package.utils.live_parallel import (
    LiveParallelPlan,
    PytestInvocation,
    build_live_parallel_plan,
    iter_plan_summary,
    pytest_n_args,
    wall_limit_sec,
)

TEST_PATH = "src/crawler/tests/integration/test_live_crawl_guarantee.py"


def _warn_bucket_failed(label: str, code: int) -> None:
    print(f"WARNING: bucket {label} failed with exit {code}", flush=True)


def _remaining_timeout(deadline: float) -> float | None:
    remain = deadline - time.monotonic()
    if remain <= 1.0:
        return 0.1
    return remain


def _run_invocation(
    label: str,
    sites_csv: str,
    xdist_n: str,
    extra_args: list[str],
    deadline: float,
) -> int:
    env = os.environ.copy()
    env["CRAWL_GUARANTEE_SITES"] = sites_csv
    # Clear company/type filters so sites_csv is the sole scope for this bucket.
    env.pop("CRAWL_GUARANTEE_COMPANY", None)
    env.pop("CRAWL_GUARANTEE_TYPE", None)
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        TEST_PATH,
        "-m",
        "live",
        "--tb=line",
        "-q",
        *pytest_n_args(xdist_n),
        *extra_args,
    ]
    print(f"=== LIVE BUCKET [{label}] sites={sites_csv} xdist={xdist_n or 'serial'} ===", flush=True)
    print(" ".join(cmd), flush=True)
    started = time.monotonic()
    timeout = _remaining_timeout(deadline)
    # New session so timeout can kill the whole pytest-xdist / Chromium tree.
    proc = subprocess.Popen(cmd, env=env, start_new_session=True)  # noqa: S603
    try:
        code = int(proc.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, AttributeError):
            proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        print(f"FAIL: bucket {label} exceeded shared wall deadline", flush=True)
        code = 124
    elapsed = time.monotonic() - started
    print(f"=== END [{label}] exit={code} elapsed={elapsed:.1f}s ===", flush=True)
    return code


def _run_pw_serial(
    invocations: list[PytestInvocation],
    extra: list[str],
    deadline: float,
) -> list[int]:
    """
    Playwright schedule: mizuho first (fast sitemap), then sekisui ∥ athome.

    One Chromium per company; overlapping sekisui with athome after mizuho keeps
    wall ≈ mizuho + max(sekisui, athome) instead of the full serial sum.
    """
    if not invocations:
        return []
    mizuho = [inv for inv in invocations if inv.label == "pw-mizuho"]
    rest = [inv for inv in invocations if inv.label != "pw-mizuho"]
    codes_by_label: dict[str, int] = {}

    for inv in mizuho:
        code = _run_invocation(inv.label, inv.sites_csv, inv.xdist_n, extra, deadline)
        codes_by_label[inv.label] = code
        if code != 0:
            _warn_bucket_failed(inv.label, code)

    if len(rest) <= 1:
        for inv in rest:
            code = _run_invocation(inv.label, inv.sites_csv, inv.xdist_n, extra, deadline)
            codes_by_label[inv.label] = code
            if code != 0:
                _warn_bucket_failed(inv.label, code)
    elif rest:
        with ThreadPoolExecutor(max_workers=len(rest)) as pool:
            futures = {
                pool.submit(
                    _run_invocation,
                    inv.label,
                    inv.sites_csv,
                    inv.xdist_n,
                    extra,
                    deadline,
                ): inv
                for inv in rest
            }
            for fut in as_completed(futures):
                inv = futures[fut]
                code = int(fut.result())
                codes_by_label[inv.label] = code
                if code != 0:
                    _warn_bucket_failed(inv.label, code)

    return [codes_by_label.get(inv.label, 1) for inv in invocations]


def _run_invocations_serial(
    invocations: list[PytestInvocation],
    extra: list[str],
    deadline: float,
) -> list[int]:
    codes: list[int] = []
    for inv in invocations:
        code = _run_invocation(inv.label, inv.sites_csv, inv.xdist_n, extra, deadline)
        codes.append(code)
        if code != 0:
            _warn_bucket_failed(inv.label, code)
    return codes


def _run_static_overlapped_with_pw(
    static_inv: PytestInvocation,
    pw: list[PytestInvocation],
    extra: list[str],
    deadline: float,
) -> dict[str, int]:
    """
    Overlap static with the Playwright serial chain (one Chromium company at a time).

    Wall ≈ max(static, sum(pw_serial)). mizuho is first because sitemap smoke is fast.
    Running all PW companies concurrently starves Docker Desktop CPU and hits the
    shared 300s wall on sekisui/athome/static.
    """
    exit_by_label: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(
                _run_invocation,
                static_inv.label,
                static_inv.sites_csv,
                static_inv.xdist_n,
                extra,
                deadline,
            ): ("static", static_inv),
            pool.submit(_run_pw_serial, pw, extra, deadline): ("pw-group", pw),
        }
        for fut in as_completed(futures):
            kind, payload = futures[fut]
            result = fut.result()
            if kind == "static":
                exit_by_label[static_inv.label] = int(result)
                if result != 0:
                    _warn_bucket_failed(static_inv.label, int(result))
                continue
            for inv, code in zip(payload, result):
                exit_by_label[inv.label] = int(code)
    return exit_by_label


def _run_plan(plan: LiveParallelPlan, extra: list[str], deadline: float) -> list[int]:
    """
    Overlap static HTML bucket with Playwright serial chain.

    Wall ≈ max(static, sum(pw_serial)) instead of static+sum(pw).
    """
    static = [inv for inv in plan.invocations if inv.label == "static"]
    pw = [inv for inv in plan.invocations if inv.label != "static"]
    if not static:
        return _run_pw_serial(pw, extra, deadline)
    if not pw:
        return _run_invocations_serial(static, extra, deadline)
    exit_by_label = _run_static_overlapped_with_pw(static[0], pw, extra, deadline)
    return [exit_by_label.get(inv.label, 1) for inv in plan.invocations]


def main(argv: list[str] | None = None) -> int:
    extra = list(argv if argv is not None else sys.argv[1:])
    jobs = jobs_from_env()
    plan = build_live_parallel_plan(jobs)
    for line in iter_plan_summary(plan):
        print(line, flush=True)
    if not plan.invocations:
        print("No jobs selected; nothing to run.", flush=True)
        return 0

    wall_limit = wall_limit_sec()
    wall0 = time.monotonic()
    deadline = wall0 + wall_limit
    exit_codes = _run_plan(plan, extra, deadline)
    wall = time.monotonic() - wall0
    failed = [c for c in exit_codes if c != 0]
    print(
        f"LIVE_PARALLEL_DONE mode={plan.mode} buckets={len(plan.invocations)} "
        f"exits={exit_codes} wall_sec={wall:.1f} limit={wall_limit:.0f}",
        flush=True,
    )
    # Allow small scheduler jitter past the nominal wall (subprocess teardown).
    if wall > wall_limit + 2.0:
        print(
            f"FAIL: wall-clock {wall:.1f}s exceeds {wall_limit:.0f}s limit",
            flush=True,
        )
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
