"""Unified Site Registry (SSOT) for crawler, dispatcher, task distribution, URL router, and ML valuation (Issue #1151).

Centralizes site metadata and provides automated 10-point wiring verification so that
adding or modifying a real-estate site via `/onboard-new-site` never results in partial wiring.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

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

    _custom_sites: ClassVar[dict[str, SiteDefinition]] = {}

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

    @classmethod
    def detect_company_from_model(cls, model_or_item: Any) -> str:
        """Detect registered company code from a Django model class or entity instance."""
        if model_or_item is None:
            return "unknown"
        cls_obj = model_or_item if isinstance(model_or_item, type) else model_or_item.__class__
        name = getattr(cls_obj, "__name__", "").lower()
        if not name:
            return "unknown"
        for comp in sorted(cls.get_all_sites().keys(), key=len, reverse=True):
            if name.startswith(comp):
                return comp
        return "unknown"

    @staticmethod
    def _infer_canonical_property_type(model_name_lower: str) -> str:
        if any(k in model_name_lower for k in ("investmentkodate", "investment_kodate", "invest_kodate")):
            return "invest_kodate"
        if any(k in model_name_lower for k in ("investment", "invest", "apartment", "building")):
            return "apartment"
        if "mansion" in model_name_lower:
            return "mansion"
        if "kodate" in model_name_lower:
            return "kodate"
        if "tochi" in model_name_lower or "land" in model_name_lower:
            return "tochi"
        return "unknown"

    @classmethod
    def get_all_property_model_entries(
        cls,
        skip_portals: bool = False,
        skip_uncrawled: bool = False,
    ) -> list[tuple[Any, str, str]]:
        """Return (model_cls, company, canonical_property_type) for all concrete property models."""
        from django.apps import apps

        from package.models.base import PropertyBaseModel

        portal_set = {c.lower() for c in PORTAL_COMPANIES}
        uncrawled_set = {c.lower() for c in UNCRAWLED_COMPANIES}
        entries: list[tuple[Any, str, str]] = []
        for model in apps.get_app_config("package").get_models():
            if not issubclass(model, PropertyBaseModel) or model._meta.abstract:
                continue
            comp = cls.detect_company_from_model(model)
            if comp == "unknown":
                continue
            if skip_portals and comp in portal_set:
                continue
            if skip_uncrawled and comp in uncrawled_set:
                continue
            ptype = cls._infer_canonical_property_type(model.__name__.lower())
            entries.append((model, comp, ptype))
        return entries

    @staticmethod
    def _candidate_model_suffixes(norm_ptype: str) -> tuple[str, ...]:
        alias_map: dict[str, tuple[str, ...]] = {
            "mansion": ("mansion",),
            "kodate": ("kodate",),
            "tochi": ("tochi",),
            "invest_kodate": ("investmentkodate", "investment", "kodate"),
            "investment_kodate": ("investmentkodate", "investment", "kodate"),
            "investmentkodate": ("investmentkodate", "investment", "kodate"),
            "invest_apartment": ("investmentapartment", "investment", "investmentbuilding"),
            "investmentapartment": ("investmentapartment", "investment", "investmentbuilding"),
            "apartment": ("investmentapartment", "investment", "investmentbuilding"),
            "investment": ("investment", "investmentapartment", "investmentbuilding"),
            "invest_building": ("investmentbuilding", "investmentapartment", "investment"),
            "investmentbuilding": ("investmentbuilding", "investmentapartment", "investment"),
        }
        return alias_map.get(norm_ptype, (norm_ptype.replace("_", ""),))

    @staticmethod
    def _route_ptype_aliases(norm_ptype: str) -> tuple[str, ...]:
        if norm_ptype in ("invest_kodate", "investment_kodate", "investmentkodate"):
            return ("invest_kodate",)
        if norm_ptype in ("apartment", "invest_apartment", "investmentapartment", "investment"):
            return ("apartment",)
        return (norm_ptype,)

    @staticmethod
    def _import_route_model(route: dict[str, Any], norm_ptype: str) -> Any | None:
        mod_name = str(route.get("model_module", ""))
        cls_name = str(route.get("model_cls", ""))
        if norm_ptype == "invest_building" and "building" not in cls_name.lower():
            return None
        try:
            mod = importlib.import_module(mod_name)
        except Exception:  # noqa: BLE001
            return None
        return getattr(mod, cls_name, None)

    @classmethod
    def _resolve_model_from_routes(cls, comp: str, norm_ptype: str) -> Any | None:
        target_ptypes = set(cls._route_ptype_aliases(norm_ptype))
        for route in UrlRouter.ROUTES:
            if str(route.get("site", "")).lower() != comp:
                continue
            if route.get("property_type") not in target_ptypes:
                continue
            resolved = cls._import_route_model(route, norm_ptype)
            if resolved is not None:
                return resolved
        return None

    @classmethod
    def resolve_model_class(cls, company: str, property_type: str) -> Any | None:
        """Resolve concrete Django property model class for any (company, property_type) or alias."""
        comp = (company or "").strip().lower()
        norm_ptype = (property_type or "").strip().lower().replace("-", "_")
        if not comp or not norm_ptype:
            return None

        from django.apps import apps

        from package.models.base import PropertyBaseModel

        company_models = [
            m
            for m in apps.get_app_config("package").get_models()
            if issubclass(m, PropertyBaseModel)
            and not m._meta.abstract
            and cls.detect_company_from_model(m) == comp
        ]
        for suffix in cls._candidate_model_suffixes(norm_ptype):
            for m in company_models:
                m_tail = m.__name__.lower()[len(comp):]
                if m_tail == suffix:
                    return m

        return cls._resolve_model_from_routes(comp, norm_ptype)


def _check_route_models_for_company(comp: str) -> list[str]:
    errs: list[str] = []
    for route in UrlRouter.ROUTES:
        if str(route.get("site", "")).lower() != comp:
            continue
        mod_name = str(route.get("model_module", ""))
        cls_name = str(route.get("model_cls", ""))
        try:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, cls_name):
                errs.append(f"UrlRouter route model class missing for {comp}: {mod_name}.{cls_name}")
        except Exception as exc:  # noqa: BLE001
            errs.append(f"UrlRouter route model import failed for {comp} ({mod_name}): {exc}")
    return errs


def _check_single_site_definition(
    comp: str,
    sdef: SiteDefinition,
    package_dir: Path,
    ml_set: set[str],
    router_sites: set[str],
) -> list[str]:
    errs: list[str] = []
    parser_file = package_dir / "parser" / f"{comp}Parser.py"
    if not parser_file.exists():
        errs.append(f"Parser file missing for {comp}: {parser_file}")
    else:
        try:
            importlib.import_module(sdef.parser_module)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"Parser module import failed for {comp} ({sdef.parser_module}): {exc}")

    model_stem = sdef.model_module.rsplit(".", 1)[-1]
    model_file = package_dir / "models" / f"{model_stem}.py"
    if not model_file.exists():
        errs.append(f"Model file missing for {comp}: {model_file}")

    if sdef.in_ml_companies and comp not in ml_set:
        errs.append(f"ML COMPANIES (package/ml/constants.py) missing company: {comp}")

    if comp not in router_sites:
        errs.append(f"UrlRouter.ROUTES missing site route for company: {comp}")
    else:
        errs.extend(_check_route_models_for_company(comp))

    if not sdef.property_types:
        errs.append(f"SiteDefinition for {comp} has 0 property_types")
    return errs


def _check_dispatch_and_models(
    all_jobs: list[tuple[str, str]],
    sites: dict[str, SiteDefinition],
    package_dir: Path,
) -> list[str]:
    missing: list[str] = []
    try:
        main_mod = importlib.import_module("main")
        dispatch_map = main_mod.get_dispatch_map()
        if not dispatch_map:
            missing.append("main.get_dispatch_map returned empty dispatch map")
    except Exception as exc:  # noqa: BLE001
        missing.append(f"main.get_dispatch_map import failed: {exc}")
        dispatch_map = {}

    if dispatch_map:
        missing.extend(
            f"main.get_dispatch_map missing job ({comp!r}, {ptype!r})"
            for comp, ptype in all_jobs
            if (comp, ptype) not in dispatch_map
        )

    router_sites = {str(r.get("site", "")).lower() for r in UrlRouter.ROUTES}
    ml_set = {c.lower() for c in ML_COMPANIES}

    for comp, sdef in sites.items():
        missing.extend(_check_single_site_definition(comp, sdef, package_dir, ml_set, router_sites))

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
