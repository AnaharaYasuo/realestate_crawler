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
from typing import Any

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


def _lit(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _route_http_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _lit(node.value)
        if value and value.startswith("http"):
            constants[target.id] = value
    return constants


def _load_get_start_url_ns(
    tree: ast.AST, path: Path, constants: dict[str, str] | None = None
) -> dict[str, Any]:
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "get_start_url":
            continue
        helper_src = ast.unparse(node)
        local_ns: dict[str, Any] = {"urllib": __import__("urllib")}
        if constants:
            local_ns.update(constants)
        try:
            exec(compile(helper_src, str(path), "exec"), local_ns)  # noqa: S102
            return local_ns
        except (SyntaxError, TypeError, ValueError, NameError) as exc:
            # Best-effort seed discovery; bad route helpers must not abort catalog load.
            _ = exc
            return {}
    return {}


def _url_from_main_call_arg(
    arg0: ast.AST,
    constants: dict[str, str],
    local_ns: dict[str, Any],
) -> str | None:
    value = _lit(arg0)
    if value and value.startswith("http"):
        return value
    if isinstance(arg0, ast.Name) and arg0.id in constants:
        return constants[arg0.id]
    if not (
        isinstance(arg0, ast.Call)
        and isinstance(arg0.func, ast.Name)
        and arg0.func.id == "get_start_url"
        and "get_start_url" in local_ns
    ):
        return None
    arg = _lit(arg0.args[0]) if arg0.args else None
    try:
        if arg is None:
            return local_ns["get_start_url"]()
        return local_ns["get_start_url"](arg)
    except (TypeError, ValueError, KeyError, AttributeError, NameError):
        return None


def _append_url_assign(child: ast.Assign, urls: list[str]) -> None:
    for target in child.targets:
        if not isinstance(target, ast.Name) or target.id != "url":
            continue
        value = _lit(child.value)
        if value and value.startswith("http"):
            urls.append(value)


def _append_main_call_url(
    child: ast.Call,
    constants: dict[str, str],
    local_ns: dict[str, Any],
    urls: list[str],
) -> None:
    if not (
        isinstance(child.func, ast.Attribute)
        and child.func.attr == "main"
        and child.args
    ):
        return
    resolved = _url_from_main_call_arg(child.args[0], constants, local_ns)
    if resolved:
        urls.append(resolved)


def _extract_cname_from_call(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name) and func.id.endswith("StartAsync"):
        return func.id
    if isinstance(func, ast.Attribute) and func.attr.endswith("StartAsync"):
        return func.attr
    if isinstance(func, ast.Attribute) and func.attr == "main" and isinstance(func.value, ast.Call):
        caller = func.value.func
        if isinstance(caller, ast.Name) and caller.id.endswith("StartAsync"):
            return caller.id
        if isinstance(caller, ast.Attribute) and caller.attr.endswith("StartAsync"):
            return caller.attr
    return None


def _collect_start_func_info(
    node: ast.FunctionDef,
    constants: dict[str, str],
    local_ns: dict[str, Any],
) -> tuple[list[str], list[str]]:
    urls: list[str] = []
    classes: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            cname = _extract_cname_from_call(child.func)
            if cname and cname not in classes:
                classes.append(cname)
            _append_main_call_url(child, constants, local_ns, urls)
        elif isinstance(child, ast.Assign):
            _append_url_assign(child, urls)
    return urls, classes


def _extract_node_info(
    node: ast.AST,
    constants: dict[str, str],
    local_ns: dict[str, Any],
    seeds: dict[str, list[str]],
    classes: dict[str, list[str]],
) -> None:
    if isinstance(node, ast.FunctionDef) and node.name.endswith(("Start", "_start")):
        u, c = _collect_start_func_info(node, constants, local_ns)
        seeds[node.name] = u
        if c:
            classes[node.name] = c
    elif isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
            val_id = node.value.id
            if val_id in seeds:
                seeds[target.id] = seeds[val_id]
            if val_id in classes:
                classes[target.id] = classes[val_id]


def _process_route_file(
    path: Path, seeds: dict[str, list[str]], classes: dict[str, list[str]]
) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    constants = _route_http_constants(tree)
    local_ns = _load_get_start_url_ns(tree, path, constants)
    for node in tree.body:
        _extract_node_info(node, constants, local_ns, seeds, classes)


def _extract_route_info() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    seeds: dict[str, list[str]] = {}
    classes: dict[str, list[str]] = {}
    for path in sorted(_ROUTES_DIR.glob("*_routes.py")):
        _process_route_file(path, seeds, classes)
    return seeds, classes


def _urls_from_url_list_value(value: ast.AST, constants: dict[str, str] | None = None) -> list[str]:
    urls: list[str] = []
    if not isinstance(value, (ast.List, ast.Tuple)):
        return urls
    for elt in value.elts:
        lit = _lit(elt)
        if not lit and isinstance(elt, ast.Name) and constants and elt.id in constants:
            lit = constants[elt.id]
        if lit:
            urls.append(lit)
    return urls


def _urls_from_assign_item(item: ast.AST, constants: dict[str, str] | None = None) -> list[str] | None:
    """Extract urlList values from Assign or AnnAssign, else None."""
    if isinstance(item, ast.Assign):
        for target in item.targets:
            if isinstance(target, ast.Name) and target.id in ("urlList", "url_list"):
                return _urls_from_url_list_value(item.value, constants)
        return None
    if isinstance(item, ast.AnnAssign):
        target = item.target
        if (
            isinstance(target, ast.Name)
            and target.id in ("urlList", "url_list")
            and item.value is not None
        ):
            return _urls_from_url_list_value(item.value, constants)
    return None


def _url_list_from_class(node: ast.ClassDef, constants: dict[str, str] | None = None) -> list[str] | None:
    """Read class-level urlList from Assign or AnnAssign (incl. ClassVar[list[str]])."""
    for item in node.body:
        urls = _urls_from_assign_item(item, constants)
        if urls is not None:
            return urls
    return None


def _extract_url_lists_from_file(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    constants = _route_http_constants(tree)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("StartAsync"):
            continue
        urls = _url_list_from_class(node, constants)
        if urls is not None:
            result[f"{path.stem}.{node.name}"] = urls
    return result


def _extract_url_lists() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted(_API_DIR.glob("*.py")):
        result.update(_extract_url_lists_from_file(path))
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
    snake_token = {
        "mansion": "mansion",
        "kodate": "kodate",
        "tochi": "tochi",
        "invest_kodate": "invest_kodate",
        "invest_apartment": "invest_apartment",
        "investment": "investment",
    }[ptype]
    return [
        f"{company}{token}Start",
        f"{company}_{snake_token}_start",
        f"{company}{token}_start",
        f"{company}_{token.lower()}_start",
    ]


def _class_matches_ptype(class_name: str, company: str, ptype: str, type_token: str) -> bool:
    lowered = class_name.lower().replace("_", "")
    if company.lower() not in lowered:
        return False
    if ptype in ("mansion", "kodate", "tochi") and "invest" in lowered:
        return False
    checks: dict[str, bool] = {
        "mansion": "mansion" in lowered,
        "kodate": "kodate" in lowered or class_name == "ParseKeikyuKodateStartAsync",
        "tochi": "tochi" in lowered,
        "invest_kodate": "kodate" in lowered and "invest" in lowered,
        "invest_apartment": "apartment" in lowered,
        "investment": (
            "investment" in lowered
            and "kodate" not in lowered
            and "apartment" not in lowered
        ),
    }
    if checks.get(ptype):
        return True
    return type_token in lowered


def _match_classes_in_module(
    module_name: str, company: str, ptype: str, type_token: str
) -> list[str]:
    path = _API_DIR / f"{module_name}.py"
    if not path.exists():
        return []
    classes = re.findall(r"class\s+(Parse\w+StartAsync)\b", path.read_text(encoding="utf-8"))
    return [
        class_name
        for class_name in classes
        if _class_matches_ptype(class_name, company, ptype, type_token)
    ]


def _match_start_class(company: str, ptype: str) -> tuple[str | None, str | None]:
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
        matches = _match_classes_in_module(module_name, company, ptype, type_token)
        if matches:
            # Prefer names that include the type token explicitly
            matches.sort(
                key=lambda name: 0 if type_token in name.lower().replace("_", "") else 1
            )
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
    route_seeds, _ = _extract_route_info()
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
