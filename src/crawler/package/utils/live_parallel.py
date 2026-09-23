"""
Local vs CI parallel schedules for live crawl-guarantee tests.

Local (Docker Desktop): cap xdist workers + serialize Playwright companies.
CI (GitHub Actions): -n auto for static HTML jobs; still serialize Playwright.
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from package.utils.crawl_jobs import CRAWL_JOBS

# Keep in sync with crawl_smoke_engine.PLAYWRIGHT_COMPANIES
PLAYWRIGHT_COMPANIES = frozenset({"athome", "mizuho", "sekisui"})
# Order: mizuho sitemap is fastest; sekisui/athome after with remaining wall.
PLAYWRIGHT_COMPANY_ORDER = ("mizuho", "sekisui", "athome")

LiveParallelMode = Literal["local", "ci"]

DEFAULT_LOCAL_XDIST = "4"
DEFAULT_CI_XDIST = "auto"
DEFAULT_WALL_LIMIT_SEC = 300.0
# With one Chromium company at a time, local static can use the full worker cap.
DEFAULT_LOCAL_XDIST_WITH_PW = "4"


def wall_limit_sec(environ: Mapping[str, str] | None = None) -> float:
    """Suite wall-clock limit (seconds). Override with CRAWL_LIVE_WALL_LIMIT_SEC."""
    env = environ if environ is not None else os.environ
    raw = (env.get("CRAWL_LIVE_WALL_LIMIT_SEC") or "").strip()
    if not raw:
        return DEFAULT_WALL_LIMIT_SEC
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_WALL_LIMIT_SEC


@dataclass(frozen=True)
class PytestInvocation:
    """One pytest process: optional site filter + xdist worker count."""

    label: str
    sites_csv: str
    xdist_n: str


@dataclass(frozen=True)
class LiveParallelPlan:
    mode: LiveParallelMode
    invocations: tuple[PytestInvocation, ...]


def detect_live_parallel_mode(
    environ: Mapping[str, str] | None = None,
) -> LiveParallelMode:
    env = environ if environ is not None else os.environ
    override = (env.get("CRAWL_LIVE_PARALLEL_MODE") or "").strip().lower()
    if override in ("local", "ci"):
        return override  # type: ignore[return-value]
    if (env.get("GITHUB_ACTIONS") or "").lower() == "true":
        return "ci"
    if (env.get("CI") or "").lower() in ("true", "1", "yes"):
        return "ci"
    return "local"


def pytest_n_args(xdist_n: str) -> list[str]:
    n = (xdist_n or "0").strip()
    if n in ("", "0", "none", "off"):
        return []
    return ["-n", n]


def _static_xdist_n(
    mode: LiveParallelMode,
    env: Mapping[str, str],
    *,
    has_playwright: bool = False,
) -> str:
    if mode == "ci":
        return (env.get("CRAWL_LIVE_XDIST_CI") or DEFAULT_CI_XDIST).strip() or DEFAULT_CI_XDIST
    if has_playwright:
        # Leave CPU for Chromium when static ∥ PW companies.
        return (
            env.get("CRAWL_LIVE_XDIST_LOCAL") or DEFAULT_LOCAL_XDIST_WITH_PW
        ).strip() or DEFAULT_LOCAL_XDIST_WITH_PW
    return (env.get("CRAWL_LIVE_XDIST_LOCAL") or DEFAULT_LOCAL_XDIST).strip() or DEFAULT_LOCAL_XDIST


def build_live_parallel_plan(
    jobs: Sequence[tuple[str, str]] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> LiveParallelPlan:
    """
    Split selected CRAWL_JOBS into:
      1) one static HTML bucket (all non-Playwright companies)
      2) one serial bucket per Playwright company (mizuho / sekisui / athome)
         — runner overlaps these with each other and with static.
    """
    env = environ if environ is not None else os.environ
    mode = detect_live_parallel_mode(env)
    selected = list(jobs if jobs is not None else CRAWL_JOBS)

    static_job_ids: list[str] = []
    pw_present: set[str] = set()
    for company, ptype in selected:
        key = company.lower()
        if key in PLAYWRIGHT_COMPANIES:
            pw_present.add(key)
            continue
        static_job_ids.append(f"{company}_{ptype}")

    invocations: list[PytestInvocation] = []
    if static_job_ids:
        invocations.append(
            PytestInvocation(
                label="static",
                sites_csv=",".join(static_job_ids),
                xdist_n=_static_xdist_n(mode, env, has_playwright=bool(pw_present)),
            )
        )
    for company in PLAYWRIGHT_COMPANY_ORDER:
        if company not in pw_present:
            continue
        # Prefer job-id list for this PW company so TYPE filters stay precise.
        pw_ids = [
            f"{c}_{p}"
            for c, p in selected
            if c.lower() == company
        ]
        invocations.append(
            PytestInvocation(
                label=f"pw-{company}",
                sites_csv=",".join(pw_ids) if pw_ids else company,
                xdist_n="0",
            )
        )
    return LiveParallelPlan(mode=mode, invocations=tuple(invocations))


def iter_plan_summary(plan: LiveParallelPlan) -> Iterable[str]:
    yield f"mode={plan.mode} buckets={len(plan.invocations)}"
    for inv in plan.invocations:
        n = inv.xdist_n if inv.xdist_n not in ("0", "") else "serial"
        yield f"  [{inv.label}] sites={inv.sites_csv} xdist={n}"
