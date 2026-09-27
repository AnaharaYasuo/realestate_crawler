"""
Local vs CI parallel schedules for live crawl-guarantee tests.

Local (Docker Desktop): cap xdist workers + serialize Playwright companies.
CI (GitHub Actions): -n auto for static HTML jobs; still serialize Playwright.

CI splits the suite across matrix jobs via:
  CRAWL_LIVE_BUCKETS       comma-separated bucket labels to keep (static, pw-<company>)
  CRAWL_LIVE_STATIC_SHARD  k/n round-robin shard of the static bucket
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
STATIC_BUCKET_LABEL = "static"
KNOWN_BUCKET_LABELS = frozenset(
    {STATIC_BUCKET_LABEL, *(f"pw-{c}" for c in PLAYWRIGHT_COMPANY_ORDER)}
)

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


def parse_static_shard(env: Mapping[str, str]) -> tuple[int, int] | None:
    """CRAWL_LIVE_STATIC_SHARD=k/n -> (k, n); None when unset. Raises on malformed input."""
    raw = (env.get("CRAWL_LIVE_STATIC_SHARD") or "").strip()
    if not raw:
        return None
    parts = raw.split("/")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"CRAWL_LIVE_STATIC_SHARD must be 'k/n', got {raw!r}")
    k, n = (int(p) for p in parts)
    if n < 1 or not 1 <= k <= n:
        raise ValueError(f"CRAWL_LIVE_STATIC_SHARD requires 1 <= k <= n, got {raw!r}")
    return k, n


def parse_bucket_filter(env: Mapping[str, str]) -> frozenset[str] | None:
    """CRAWL_LIVE_BUCKETS -> label set; None when unset. Raises on unknown labels."""
    raw = env.get("CRAWL_LIVE_BUCKETS")
    if raw is None or not raw.strip():
        return None
    labels = frozenset(s.strip().lower() for s in raw.split(",") if s.strip())
    if not labels:
        raise ValueError(f"CRAWL_LIVE_BUCKETS has no labels: {raw!r}")
    unknown = labels - KNOWN_BUCKET_LABELS
    if unknown:
        raise ValueError(
            f"CRAWL_LIVE_BUCKETS has unknown labels {sorted(unknown)}; "
            f"allowed: {sorted(KNOWN_BUCKET_LABELS)}"
        )
    return labels


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

    Then narrow by CRAWL_LIVE_STATIC_SHARD (static jobs only) and
    CRAWL_LIVE_BUCKETS (bucket labels). Invalid values raise ValueError.
    """
    env = environ if environ is not None else os.environ
    mode = detect_live_parallel_mode(env)
    shard = parse_static_shard(env)
    bucket_filter = parse_bucket_filter(env)
    selected = list(jobs if jobs is not None else CRAWL_JOBS)

    static_job_ids: list[str] = []
    pw_present: set[str] = set()
    for company, ptype in selected:
        key = company.lower()
        if key in PLAYWRIGHT_COMPANIES:
            pw_present.add(key)
            continue
        static_job_ids.append(f"{company}_{ptype}")

    if shard is not None:
        k, n = shard
        static_job_ids = [j for i, j in enumerate(static_job_ids) if i % n == k - 1]

    invocations: list[PytestInvocation] = []
    if static_job_ids:
        invocations.append(
            PytestInvocation(
                label=STATIC_BUCKET_LABEL,
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
    if bucket_filter is not None:
        invocations = [inv for inv in invocations if inv.label in bucket_filter]
    return LiveParallelPlan(mode=mode, invocations=tuple(invocations))


def iter_plan_summary(plan: LiveParallelPlan) -> Iterable[str]:
    yield f"mode={plan.mode} buckets={len(plan.invocations)}"
    for inv in plan.invocations:
        n = inv.xdist_n if inv.xdist_n not in ("0", "") else "serial"
        yield f"  [{inv.label}] sites={inv.sites_csv} xdist={n}"
