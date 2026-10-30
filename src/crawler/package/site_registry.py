"""Unified Site Registry (SSOT) for crawler, dispatcher, task distribution, URL router, and ML valuation (Issue #1151).

Centralizes site metadata and provides automated 10-point wiring verification so that
adding or modifying a real-estate site via `/onboard-new-site` never results in partial wiring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any

from package.ml.constants import COMPANIES as ML_COMPANIES
from package.utils.crawl_jobs import CRAWL_JOBS, PORTAL_COMPANIES, UNCRAWLED_COMPANIES
from package.utils.task_distribution import distribute_jobs
from package.utils.url_router import UrlRouter

MID_BROKER_MODEL_COMPANIES = frozenset({"ietan", "haseko", "adcast", "toho"})


@dataclass(frozen=True)
class SiteDefinition:
    """Canonical metadata definition for a real-estate crawler site."""

    company: str
    property_types: tuple[str, ...]
    parser_module: str
    model_module: str
    is_portal: bool = False
    is_uncrawled: bool = False
    in_ml_companies: bool = True
    extra_metadata: dict[str, Any] = field(default_factory=dict)


class SiteRegistry:
    """Single Source of Truth registry for all crawler sites and jobs."""

    _custom_sites: dict[str, SiteDefinition] = {}

    @classmethod
    def register_site(cls, site_def: SiteDefinition) -> None:
        """Register or override a site definition dynamically."""
        cls._custom_sites[site_def.company.lower()] = site_def

    @classmethod
    def get_all_jobs(cls) -> list[tuple[str, str]]:
        """Return all registered (company, property_type) crawl jobs."""
        jobs = list(CRAWL_JOBS)
        existing = set(jobs)
        for comp, sdef in cls._custom_sites.items():
            for ptype in sdef.property_types:
                pair = (comp, ptype)
                if pair not in existing:
                    jobs.append(pair)
                    existing.add(pair)
        return jobs

    @classmethod
    def get_all_sites(cls) -> dict[str, SiteDefinition]:
        """Build and return the complete dictionary of SiteDefinitions keyed by company code."""
        by_company: dict[str, list[str]] = {}
        for comp, ptype in CRAWL_JOBS:
            c = comp.lower()
            by_company.setdefault(c, [])
            if ptype not in by_company[c]:
                by_company[c].append(ptype)

        ml_set = {c.lower() for c in ML_COMPANIES}
        portal_set = {c.lower() for c in PORTAL_COMPANIES}
        uncrawled_set = {c.lower() for c in UNCRAWLED_COMPANIES}

        sites: dict[str, SiteDefinition] = {}
        for comp, ptypes in by_company.items():
            model_mod = (
                "package.models.mid_brokers"
                if comp in MID_BROKER_MODEL_COMPANIES
                else f"package.models.{comp}"
            )
            sites[comp] = SiteDefinition(
                company=comp,
                property_types=tuple(ptypes),
                parser_module=f"package.parser.{comp}Parser",
                model_module=model_mod,
                is_portal=comp in portal_set,
                is_uncrawled=comp in uncrawled_set,
                in_ml_companies=comp in ml_set,
            )

        sites.update(cls._custom_sites)
        return sites


def _check_dispatch_and_models(
    all_jobs: list[tuple[str, str]],
    sites: dict[str, SiteDefinition],
    package_dir: Path,
) -> list[str]:
    missing: list[str] = []
    try:
        main_mod = importlib.import_module("main")
        dispatch_map = main_mod.get_dispatch_map()
    except Exception as exc:  # noqa: BLE001
        missing.append(f"main.get_dispatch_map import failed: {exc}")
        dispatch_map = {}

    for comp, ptype in all_jobs:
        if dispatch_map and (comp, ptype) not in dispatch_map:
            missing.append(f"main.get_dispatch_map missing job ({comp!r}, {ptype!r})")

    router_sites = {str(r.get("site", "")).lower() for r in UrlRouter.ROUTES}
    ml_set = {c.lower() for c in ML_COMPANIES}

    for comp, sdef in sites.items():
        parser_file = package_dir / "parser" / f"{comp}Parser.py"
        if not parser_file.exists():
            missing.append(f"Parser file missing for {comp}: {parser_file}")

        model_stem = sdef.model_module.rsplit(".", 1)[-1]
        model_file = package_dir / "models" / f"{model_stem}.py"
        if not model_file.exists():
            missing.append(f"Model file missing for {comp}: {model_file}")

        if comp not in ml_set:
            missing.append(f"ML COMPANIES (package/ml/constants.py) missing company: {comp}")

        if comp not in router_sites:
            missing.append(f"UrlRouter.ROUTES missing site route for company: {comp}")

        if not sdef.property_types:
            missing.append(f"SiteDefinition for {comp} has 0 property_types")

    return missing


def _check_task_distribution(all_jobs: list[tuple[str, str]]) -> list[str]:
    missing: list[str] = []
    expected_set = set(all_jobs)
    for task_count in (3, 4, 8):
        distributed: list[tuple[str, str]] = []
        for idx in range(task_count):
            distributed.extend(distribute_jobs(all_jobs, task_index=idx, task_count=task_count))
        dist_set = set(distributed)
        dropped = expected_set - dist_set
        if dropped:
            missing.append(f"distribute_jobs(task_count={task_count}) dropped jobs: {sorted(dropped)}")
        if len(distributed) != len(all_jobs):
            missing.append(
                f"distribute_jobs(task_count={task_count}) count mismatch: {len(distributed)} != {len(all_jobs)}"
            )
    return missing


def verify_all_registered_sites() -> dict[str, Any]:
    """Verify 10-point wiring integrity across all registered sites and jobs."""
    sites = SiteRegistry.get_all_sites()
    all_jobs = SiteRegistry.get_all_jobs()
    package_dir = Path(__file__).resolve().parent

    missing = _check_dispatch_and_models(all_jobs, sites, package_dir)
    missing.extend(_check_task_distribution(all_jobs))

    return {
        "total_sites": len(sites),
        "total_jobs": len(all_jobs),
        "missing": missing,
        "sites": {
            comp: {
                "property_types": list(sdef.property_types),
                "parser_module": sdef.parser_module,
                "model_module": sdef.model_module,
                "is_portal": sdef.is_portal,
                "in_ml_companies": sdef.in_ml_companies,
            }
            for comp, sdef in sites.items()
        },
    }
