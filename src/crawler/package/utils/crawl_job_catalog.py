# -*- coding: utf-8 -*-
"""
Crawl job catalog: resolve Start API + seed URL for every CRAWL_JOBS entry.

Discovery is AST-based (no Django import required) so offline unit tests stay light.
"""
from __future__ import annotations

import ast
import importlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from package.utils.crawl_jobs import CRAWL_JOBS

_CRAWLER_ROOT = Path(__file__).resolve().parents[2]
_ROUTES_DIR = _CRAWLER_ROOT / "routes"
_API_DIR = _CRAWLER_ROOT / "package" / "api"


@dataclass(frozen=True)
class CrawlTarget:
    company: str
    property_type: str
    api_module: str
    start_class: str
    seed_url: str

    @property
    def job_id(self) -> str:
        return f"{self.company}_{self.property_type}"


def _lit(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_route_seeds() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(_ROUTES_DIR.glob("*_routes.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        constants: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    value = _lit(node.value)
                    if value and value.startswith("http"):
                        constants[target.id] = value

        local_ns: dict[str, Any] = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "get_start_url":
                helper_src = ast.unparse(node)
                local_ns = {"urllib": __import__("urllib")}
                try:
                    exec(compile(helper_src, str(path), "exec"), local_ns)  # noqa: S102
                except Exception:
                    local_ns = {}

        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.endswith("Start"):
                continue
            urls: list[str] = []
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "main"
                    and child.args
                ):
                    arg0 = child.args[0]
                    value = _lit(arg0)
                    if value and value.startswith("http"):
                        urls.append(value)
                    elif isinstance(arg0, ast.Name) and arg0.id in constants:
                        urls.append(constants[arg0.id])
                    elif (
                        isinstance(arg0, ast.Call)
                        and isinstance(arg0.func, ast.Name)
                        and arg0.func.id == "get_start_url"
                        and "get_start_url" in local_ns
                    ):
                        arg = _lit(arg0.args[0]) if arg0.args else None
                        try:
                            urls.append(
                                local_ns["get_start_url"]()
                                if arg is None
                                else local_ns["get_start_url"](arg)
                            )
                        except Exception:
                            pass
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == "url":
                            value = _lit(child.value)
                            if value and value.startswith("http"):
                                urls.append(value)
            found[node.name] = urls
    return found


def _extract_url_lists() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted(_API_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("StartAsync"):
                continue
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "urlList":
                        urls: list[str] = []
                        if isinstance(item.value, (ast.List, ast.Tuple)):
                            for elt in item.value.elts:
                                value = _lit(elt)
                                if value:
                                    urls.append(value)
                        result[f"{path.stem}.{node.name}"] = urls
    return result


def _start_func_names(company: str, ptype: str) -> list[str]:
    token = {
        "mansion": "Mansion",
        "kodate": "Kodate",
        "tochi": "Tochi",
        "invest_kodate": "InvestKodate",
        "invest_apartment": "InvestApartment",
        "investment": "Investment",
    }[ptype]
    return [f"{company}{token}Start"]


def _match_start_class(company: str, ptype: str) -> tuple[Optional[str], Optional[str]]:
    """Return (api_module, start_class) for a crawl job."""
    type_token = {
        "mansion": "mansion",
        "kodate": "kodate",
        "tochi": "tochi",
        "invest_kodate": "investkodate",
        "invest_apartment": "investapartment",
        "investment": "investment",
    }[ptype]

    modules: list[str] = []
    if ptype.startswith("invest") or ptype == "investment":
        modules.extend([f"{company}_investment", company])
    else:
        modules.append(company)

    for module_name in modules:
        path = _API_DIR / f"{module_name}.py"
        if not path.exists():
            continue
        classes = re.findall(r"class\s+(Parse\w+StartAsync)\b", path.read_text(encoding="utf-8"))
        matches: list[str] = []
        for class_name in classes:
            lowered = class_name.lower().replace("_", "")
            if company.lower() not in lowered:
                continue
            if ptype in ("mansion", "kodate", "tochi") and "invest" in lowered:
                continue
            if ptype == "mansion" and "mansion" in lowered:
                matches.append(class_name)
            elif ptype == "kodate" and ("kodate" in lowered or class_name == "ParseKeikyuKodateStartAsync"):
                matches.append(class_name)
            elif ptype == "tochi" and "tochi" in lowered:
                matches.append(class_name)
            elif ptype == "invest_kodate" and "kodate" in lowered and "invest" in lowered:
                matches.append(class_name)
            elif ptype == "invest_apartment" and "apartment" in lowered:
                matches.append(class_name)
            elif (
                ptype == "investment"
                and "investment" in lowered
                and "kodate" not in lowered
                and "apartment" not in lowered
            ):
                matches.append(class_name)
            elif type_token in lowered:
                matches.append(class_name)
        if matches:
            # Prefer names that include the type token explicitly
            matches.sort(key=lambda name: 0 if type_token in name.lower().replace("_", "") else 1)
            return module_name, matches[0]
    return None, None


def _seed_from_inheritance(api_module: str, start_class: str, url_lists: dict[str, list[str]]) -> list[str]:
    direct = url_lists.get(f"{api_module}.{start_class}", [])
    if direct:
        return direct
    # Walk base classes declared in the same module (shallow)
    path = _API_DIR / f"{api_module}.py"
    if not path.exists():
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    class_bases: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_bases[node.name] = [
                base.id for base in node.bases if isinstance(base, ast.Name)
            ]
    queue = list(class_bases.get(start_class, []))
    seen = {start_class}
    while queue:
        base = queue.pop(0)
        if base in seen:
            continue
        seen.add(base)
        urls = url_lists.get(f"{api_module}.{base}", [])
        if urls:
            return urls
        queue.extend(class_bases.get(base, []))
    return []


@lru_cache(maxsize=1)
def build_catalog() -> dict[tuple[str, str], CrawlTarget]:
    route_seeds = _extract_route_seeds()
    url_lists = _extract_url_lists()
    catalog: dict[tuple[str, str], CrawlTarget] = {}
    for company, ptype in CRAWL_JOBS:
        seeds: list[str] = []
        for func_name in _start_func_names(company, ptype):
            candidate = route_seeds.get(func_name) or []
            if candidate:
                seeds = candidate
                break
        api_module, start_class = _match_start_class(company, ptype)
        if api_module and start_class and not seeds:
            seeds = _seed_from_inheritance(api_module, start_class, url_lists)
        if not api_module or not start_class or not seeds:
            continue
        catalog[(company, ptype)] = CrawlTarget(
            company=company,
            property_type=ptype,
            api_module=api_module,
            start_class=start_class,
            seed_url=seeds[0],
        )
    return catalog


def get_target(company: str, property_type: str) -> CrawlTarget:
    catalog = build_catalog()
    key = (company, property_type)
    if key not in catalog:
        raise KeyError(f"Crawl target not resolved for {company}/{property_type}")
    return catalog[key]


def unresolved_jobs() -> list[tuple[str, str]]:
    catalog = build_catalog()
    return [job for job in CRAWL_JOBS if job not in catalog]


def load_start_api_class(target: CrawlTarget):
    module = importlib.import_module(f"package.api.{target.api_module}")
    return getattr(module, target.start_class)


def load_parser_for_target(target: CrawlTarget):
    start_cls = load_start_api_class(target)
    instance = start_cls()
    if not hasattr(instance, "_generateParser"):
        raise AttributeError(f"{target.start_class} has no _generateParser()")
    return instance._generateParser()
