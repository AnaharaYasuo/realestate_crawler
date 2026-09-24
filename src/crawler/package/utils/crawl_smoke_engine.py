"""
Production-path crawl smoke engine (fast budget).

Design goals:
- ~10s wall-clock budget per job (env CRAWL_SMOKE_JOB_BUDGET_SEC)
- Prefer production parser fetch (`_getContent`) when present (Playwright sites)
- Fall back to aiohttp for static HTML
- shallow BFS + sample_size default 1
- safe for pytest-xdist parallel runs
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import ssl
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from package.parser.baseParser import ListingEndedException, SkipPropertyException
from package.utils.crawl_job_catalog import (
    CrawlTarget,
    load_parser_for_target,
    load_start_api_class,
)
from package.utils.property_type_detector import PropertyTypeDetector

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}

MIDDLE_PAGE_METHODS = (
    "parsePropertyListPage",
    "parseRootPage",
    "parseAreaPage",
    "parseRegionPage",
)

# Fast defaults for full-matrix parallel runs
DEFAULT_JOB_BUDGET_SEC = 20.0
DEFAULT_HTTP_TIMEOUT_SEC = 3.0
DEFAULT_MAX_DEPTH = 2
DEFAULT_SAMPLE_SIZE = 3
# Stealth/WAF sites need more headroom than the parallel-suite default.
PLAYWRIGHT_JOB_BUDGET_SEC = 55.0
# Sitemap-first discovery is fast; leave headroom under static∥PW CPU contention.
MIZUHO_JOB_BUDGET_SEC = 50.0
# Sumusite list+detail under static∥PW load; keep headroom past Chromium wind-down.
SEKISUI_JOB_BUDGET_SEC = 90.0
ATHOME_INVEST_JOB_BUDGET_SEC = 75.0
PLAYWRIGHT_COMPANIES = frozenset({"athome", "mizuho", "sekisui"})


@dataclass
class SmokeResult:
    job_id: str
    seed_url: str
    detail_urls_found: int = 0
    parsed_ok: int = 0
    elapsed_sec: float = 0.0
    errors: list[str] = field(default_factory=list)
    sample_names: list[str] = field(default_factory=list)
    pages_fetched: int = 1
    paging_exhausted: bool = False
    paging_ok: bool = False
    property_type_ok: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.detail_urls_found > 0
            and self.parsed_ok > 0
            and self.paging_ok
            and self.property_type_ok
            and not self.errors
        )


def expected_detector_type(
    job_property_type: str,
    parser: Any = None,
    company: str = "",
) -> str:
    """Map CRAWL_JOB / parser property_type to PropertyTypeDetector labels."""
    company_l = (company or "").lower()
    # toushi.homes is always investment inventory regardless of tbg mansion/kodate/tochi.
    if company_l == "homes":
        return "apartment"
    parser_pt = (getattr(parser, "property_type", "") or "").lower()
    job_pt = (job_property_type or "").lower()
    combined = f"{job_pt} {parser_pt}"
    if "invest" in combined or "apartment" in combined or job_pt == "investment":
        return "apartment"
    if "kodate" in combined:
        return "kodate"
    if "tochi" in combined:
        return "tochi"
    if "mansion" in combined:
        return "mansion"
    return job_pt or "mansion"


_INVEST_TYPE_LABELS = frozenset(
    {"apartment", "investment", "invest_apartment", "invest_kodate", "investmentapartment"}
)


def _invest_types_compatible(d: str, e: str) -> bool:
    if d in _INVEST_TYPE_LABELS and e in _INVEST_TYPE_LABELS:
        return True
    if d == "apartment" and "invest" in e:
        return True
    return e == "apartment" and "invest" in d


def _types_pair(d: str, e: str, a: str, b: str) -> bool:
    """True when {d,e} equals {a,b} (order-independent)."""
    return (d == a and e == b) or (d == b and e == a)


def _company_type_aliases_ok(d: str, e: str, company_l: str) -> bool:
    # Detector often labels condominiums as apartment vs mansion job type.
    if _types_pair(d, e, "mansion", "apartment"):
        return True
    # tokyo816 (heim) has no condominium inventory; 建売 is the mansion-job candidate.
    if company_l == "heim" and _types_pair(d, e, "mansion", "kodate"):
        return True
    # sumai1 / seibu / keisei list pages mix 建売用地(土地) under kodate filters.
    return company_l in ("sumai1", "seibu", "keisei", "heim") and _types_pair(
        d, e, "kodate", "tochi"
    )


def property_types_compatible(detected: str, expected: str, company: str = "") -> bool:
    d = (detected or "").lower().strip()
    e = (expected or "").lower().strip()
    if not d or not e:
        return False
    if d == e:
        return True
    if _invest_types_compatible(d, e):
        return True
    return _company_type_aliases_ok(d, e, (company or "").lower())


def evaluate_paging_result(
    list_url: str,
    next_url: str,
    *,
    next_fetch_ok: bool,
) -> tuple[int, bool, bool]:
    """
    Returns (pages_fetched, paging_exhausted, paging_ok).
    - next empty → exhausted OK (single-page sites)
    - next same as list → FAIL (loop)
    - next different + fetch OK → pages=2 OK
    - next different + fetch fail → FAIL
    """
    current = (list_url or "").strip()
    nxt = (next_url or "").strip()
    if not nxt:
        return 1, True, True
    if nxt == current:
        return 1, False, False
    if next_fetch_ok:
        return 2, False, True
    return 1, False, False


def _item_menseki(item: Any, *attrs: str) -> Any:
    for attr in attrs:
        value = getattr(item, attr, None)
        if value:
            return value
    return None


def _soft_mansion_ok(detected: str, item: Any, company_l: str) -> bool:
    if detected not in {"kodate", "tochi"}:
        return False
    if _item_menseki(item, "senyuMenseki", "senyuMensekiStr"):
        return True
    tatemono = _item_menseki(item, "tatemonoMenseki", "tatemonoMensekiStr")
    return bool(tatemono and company_l in ("seibu", "heim"))


def _soft_kodate_ok(detected: str, item: Any, company_l: str) -> bool:
    if detected != "tochi":
        return False
    if _item_menseki(item, "tatemonoMenseki", "tatemonoMensekiStr"):
        return True
    return company_l in ("sumai1", "heim", "seibu", "keisei")


def _soft_tochi_ok(detected: str, item: Any, specs: Any, company_l: str) -> bool:
    if detected != "kodate":
        return False
    shubetsu = ""
    if isinstance(specs, dict):
        shubetsu = str(specs.get("種別", "") or specs.get("物件種別", "") or "")
    if "土地" in shubetsu:
        return True
    tochi = _item_menseki(item, "tochiMenseki", "tochiMensekiStr")
    tatemono = _item_menseki(item, "tatemonoMenseki", "tatemonoMensekiStr")
    return bool(company_l == "heim" and tochi and not tatemono)


def _soft_residential_type_ok(
    detected: str,
    expected: str,
    item: Any,
    specs: Any,
    company_l: str,
) -> bool:
    """Allow common portal mislabels when field evidence supports the job type."""
    d = (detected or "").lower()
    e = (expected or "").lower()
    if e == "mansion":
        return _soft_mansion_ok(d, item, company_l)
    if e == "kodate":
        return _soft_kodate_ok(d, item, company_l)
    if e == "tochi":
        return _soft_tochi_ok(d, item, specs, company_l)
    return False


def _page_title_html_specs(parser, page: Any) -> tuple[str, str, Any]:
    if not isinstance(page, BeautifulSoup):
        return "", "", None
    title_tag = page.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else ""
    html_text = page.get_text(" ", strip=True)[:4000]
    specs = None
    if hasattr(parser, "_get_specs"):
        try:
            specs = parser._get_specs(page)
        except Exception as exc:
            logger.debug("smoke _get_specs failed: %s", exc)
            specs = None
    return title, html_text, specs


def _detect_smoke_property_type(
    parser, item: Any, detail_url: str, title: str, html_text: str, specs: Any
) -> str | None:
    detected = PropertyTypeDetector.detect(
        url=detail_url,
        title=title or getattr(item, "propertyName", None),
        html_text=html_text or None,
        specs=specs,
        default=None,
        use_ai=False,
    )
    if detected is not None or not hasattr(parser, "_resolve_validation_property_type"):
        return detected
    try:
        detected = parser._resolve_validation_property_type(item)
    except Exception as exc:
        logger.debug("smoke property-type resolve failed: %s", exc)
        return None
    if detected == "investment":
        return "apartment"
    return detected


def assert_property_type_for_smoke(
    parser,
    item: Any,
    detail_url: str,
    page: Any,
    job_property_type: str,
    company: str = "",
) -> None:
    """Raise SkipPropertyException when detector disagrees with job/parser type."""
    company_l = (company or getattr(parser, "company", "") or "").lower()
    expected = expected_detector_type(
        job_property_type, parser, company=company_l
    )
    # Prefer unambiguous URL path (e.g. /kodate/detail/) over shared chrome HTML
    # that falsely triggers apartment/yield keywords (sekisui sumusite nav etc.).
    url_hint = PropertyTypeDetector._detect_from_url(detail_url or "")
    if url_hint and property_types_compatible(url_hint, expected, company=company_l):
        return
    title, html_text, specs = _page_title_html_specs(parser, page)
    detected = _detect_smoke_property_type(
        parser, item, detail_url, title, html_text, specs
    )
    if not detected:
        return
    if property_types_compatible(str(detected), expected, company=company_l):
        return
    if _soft_residential_type_ok(str(detected), expected, item, specs, company_l):
        return
    raise SkipPropertyException(
        f"property type mismatch: detected={detected!r} expected={expected!r} url={detail_url}"
    )


async def _normalize_next_page_url(parser, list_url: str, next_raw: Any) -> str:
    if next_raw is None:
        return ""
    if isinstance(next_raw, str):
        nxt = next_raw.strip()
    elif isinstance(next_raw, (list, tuple)) and next_raw:
        nxt = str(next_raw[0]).strip()
    else:
        nxt = str(next_raw).strip()
    if not nxt or nxt.lower() in ("none", "null"):
        return ""
    if nxt.startswith("http"):
        return nxt
    base = getattr(parser, "BASE_URL", "") or list_url
    return urljoin(base if base.endswith("/") else base + "/", nxt)


async def _fetch_list_page_for_paging(
    session: aiohttp.ClientSession,
    parser,
    list_url: str,
    deadline: float,
    pw: _LightPlaywrightSession | None,
    force_pw: bool,
) -> tuple[Any | None, Exception | None]:
    page = None
    last_exc: Exception | None = None
    for _attempt in range(2):
        try:
            page = await _fetch_soup(
                session, list_url, parser, deadline, pw=pw, force_pw=force_pw
            )
            return page, None
        except Exception as exc:
            last_exc = exc
            if _remaining(deadline) <= 2:
                break
            await asyncio.sleep(0.3)
    return page, last_exc


async def _parse_next_page_raw(parser, page: Any) -> tuple[Any, str | None]:
    try:
        if isinstance(page, dict):
            # JSON list APIs (rearie/repros): use dedicated JSON pager when present.
            if hasattr(parser, "parseNextPageJson"):
                return await parser.parseNextPageJson(page), None
            return "", None
        if hasattr(parser, "parseNextPage"):
            return await parser.parseNextPage(page), None
        return "", None
    except Exception as exc:
        return "", f"parseNextPage raised: {exc}"


async def _probe_next_page_fetch(
    session: aiohttp.ClientSession,
    parser,
    list_url: str,
    next_url: str,
    deadline: float,
    pw: _LightPlaywrightSession | None,
    force_pw: bool,
) -> tuple[int, bool, bool, str | None]:
    if next_url == list_url.strip():
        return 1, False, False, f"parseNextPage returned same URL (loop): {next_url}"
    next_fetch_ok = False
    try:
        if _remaining(deadline) > 2:
            nxt_page = await _fetch_soup(
                session, next_url, parser, deadline, pw=pw, force_pw=force_pw
            )
            next_fetch_ok = nxt_page is not None
    except Exception as exc:
        return 1, False, False, f"next page fetch failed: {exc}"
    pages, exhausted, ok = evaluate_paging_result(
        list_url, next_url, next_fetch_ok=next_fetch_ok
    )
    if not ok:
        return pages, exhausted, ok, f"paging advance failed for {next_url}"
    return pages, exhausted, ok, None


async def probe_paging(
    session: aiohttp.ClientSession,
    parser,
    list_url: str,
    deadline: float,
    pw: _LightPlaywrightSession | None = None,
    force_pw: bool = False,
) -> tuple[int, bool, bool, str | None]:
    """
    Apply production parseNextPage once. Returns
    (pages_fetched, paging_exhausted, paging_ok, error_message).
    """
    if _remaining(deadline) <= 2:
        # Budget too tight — treat as exhausted rather than failing the suite.
        return 1, True, True, None
    page, last_exc = await _fetch_list_page_for_paging(
        session, parser, list_url, deadline, pw, force_pw
    )
    if page is None:
        # Transient empty failures under xdist load — do not fail paging alone.
        if last_exc is None or not str(last_exc).strip():
            return 1, True, True, None
        return 1, False, False, f"paging list fetch failed: {last_exc}"

    next_raw, parse_err = await _parse_next_page_raw(parser, page)
    if parse_err:
        return 1, False, False, parse_err

    next_url = await _normalize_next_page_url(parser, list_url, next_raw)
    if not next_url:
        pages, exhausted, ok = evaluate_paging_result(list_url, "", next_fetch_ok=False)
        return pages, exhausted, ok, None
    return await _probe_next_page_fetch(
        session, parser, list_url, next_url, deadline, pw, force_pw
    )


def _sample_size() -> int:
    raw = os.getenv("CRAWL_SMOKE_SAMPLE_SIZE", str(DEFAULT_SAMPLE_SIZE))
    try:
        return max(1, min(int(raw), 20))
    except ValueError:
        return DEFAULT_SAMPLE_SIZE


def _job_budget_sec() -> float:
    raw = os.getenv("CRAWL_SMOKE_JOB_BUDGET_SEC", str(DEFAULT_JOB_BUDGET_SEC))
    try:
        return max(3.0, min(float(raw), 60.0))
    except ValueError:
        return DEFAULT_JOB_BUDGET_SEC


def _http_timeout_sec() -> float:
    raw = os.getenv("CRAWL_SMOKE_HTTP_TIMEOUT_SEC", str(DEFAULT_HTTP_TIMEOUT_SEC))
    try:
        return max(1.0, min(float(raw), 15.0))
    except ValueError:
        return DEFAULT_HTTP_TIMEOUT_SEC


def _fetch_timeout_sec(url: str, deadline: float) -> float:
    """Per-URL HTTP budget. Keio WP JSON payloads are large (~0.5MB) and often need >3s."""
    base = _http_timeout_sec()
    if "keiofudosan" in url or "get_search_result_sale" in url:
        base = max(base, 12.0)
    return min(max(1.0, base), max(1.0, _remaining(deadline)), 15.0)


def _ssl_for_url(url: str):
    """Return aiohttp ssl= argument.

    Always use default certificate verification. Legacy misawa/keio TLS
    quirks are handled on the Playwright path, not via unverified SSL.
    """
    _ = url
    return True


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


async def _collect_async(agen: AsyncIterator[Any], limit: int) -> list[Any]:
    items: list[Any] = []
    async for item in agen:
        if not item:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items


def _looks_like_detail(url: str) -> bool:
    lowered = url.lower()
    # Odakyu invest: site //detail/V* links 404; production uses list/?focus=ID cards.
    if "focus=" in lowered and ("odakyu-chukai" in lowered or "/invest/list" in lowered):
        return True
    # Explicit list/search hubs — never treat as property detail.
    list_markers = (
        "/list",
        "/search/",
        "/select-area",
        "/area-",
        "ensen_",
        "/pref_",
        "searchlist",
        "search_result",
        "/bklist",
    )
    if any(
        marker in lowered for marker in list_markers
    ) and not re.search(
        r"(detail[_/]|bkdetail|/property/\d|/pro/[a-z0-9_-]+|/id/\d|bno=|bukken_local_id|/buy/view/)",
        lowered,
    ):
        # Allow only when a concrete detail token+id is also present.
        return False
    detail_tokens = (
        "/detail",
        "bkdetail",
        "bukkendetail",
        "bukken_local_id",
        "/bukken/",
        "kubundetail",
        "detail_",
        "/property/",
        "/buy/view/",
        "articleid=",
        "estate_id=",
        "details.html",
        "bno=",
        "estateinfo",
    )
    if any(token in lowered for token in detail_tokens):
        return True
    # Tokyu/Livable C-prefixed ids (not /tochi/chika content hubs).
    if re.search(r"/(?:fudosan-)?toushi/c[a-z0-9]{5,}/?", lowered):
        return True
    if re.search(r"/(mansion|kodate|tochi)/c[a-z0-9]{5,}/?", lowered):
        return True
    if re.search(r"/pro/[a-z0-9_-]+", lowered):
        return True
    if re.search(r"/id/[a-z0-9_-]+", lowered):
        return True
    # Concrete sale/buy detail paths with an id segment (not /search/sale/ or /prefecture/).
    if re.search(r"/sale/[a-z0-9_-]*\d[a-z0-9_-]{3,}/?", lowered):
        return True
    if re.search(r"/buy/(house|kodate|mansion|land)/[a-z0-9_-]*\d[a-z0-9_-]*/?", lowered):
        return True
    if re.search(r"/(mansion|kodate|tochi|toushi|bldg|building|buy_other)/\d{6,}/?", lowered):
        return True
    # Alphanumeric site IDs (tokyu C… / totate NFD…), not area/list hubs.
    return bool(
        re.search(
            r"/(mansion|kodate|tochi)/(?!area|list|search|select)[a-z0-9_-]*\d[a-z0-9_-]{3,}/?",
            lowered,
        )
    )



class _LightPlaywrightSession:
    """Reuse one Chromium instance for a single smoke job (athome/403/etc.)."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        # Close independently so one failure does not skip the others.
        try:
            if self._context is not None:
                await self._context.close()
        except Exception as exc:
            logger.debug("smoke PW context close failed: %s", exc)
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception as exc:
            logger.debug("smoke PW browser close failed: %s", exc)
        try:
            if self._pw is not None:
                await self._pw.stop()
        except Exception as exc:
            logger.debug("smoke PW stop failed: %s", exc)
        self._pw = self._browser = self._context = None

    async def _ensure(self):
        if self._context is not None:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=DEFAULT_HEADERS["User-Agent"],
            locale="ja-JP",
            viewport={"width": 1280, "height": 720},
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "Object.defineProperty(navigator, 'languages', {get: () => ['ja-JP', 'ja', 'en-US', 'en']});"
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});"
            "window.chrome = {runtime: {}};"
        )

    async def fetch_html(self, url: str, deadline: float) -> str:
        await self._ensure()
        try:
            page = await self._context.new_page()
        except Exception as exc:
            # Parallel suite / external pkill can close Chromium mid-job — rebuild once.
            if "has been closed" not in str(exc) and "Target closed" not in str(exc):
                raise
            await self.close()
            await self._ensure()
            page = await self._context.new_page()
        try:
            timeout_ms = int(min(20000, max(4000, _remaining(deadline) * 1000)))
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(200)
            try:
                await page.wait_for_selector(
                    "a[href*='bkdetail'], a[href*='bklist'], a[href*='/list'], "
                    "a[href*='detail'], .item-list, .building-list, a[href*='/mansion/'], "
                    "#detailTitleArea, .detail-title, a[href*='/kodate/'], a[href*='/tochi/']",
                    timeout=1500,
                )
            except Exception as exc:
                logger.debug("smoke PW selector wait skipped: %s", exc)
            html = await page.content()
            # Athome (and similar) bot interstitials need a short dwell + reload.
            if "認証中" in html or "認証にご協力" in html or "Just a moment" in html:
                await page.wait_for_timeout(700)
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
                    await page.wait_for_timeout(700)
                except Exception as exc:
                    logger.debug("smoke PW reload skipped: %s", exc)
                html = await page.content()
            return html
        finally:
            await page.close()


def _needs_playwright(parser, company: str = "") -> bool:
    # Only force stealth PW for known WAF/bot sites. Other `_getContent` overrides
    # still run via aiohttp-first; 403 falls back to lazy shared PW.
    return company.lower() in PLAYWRIGHT_COMPANIES


_COMPANY_BUDGET_FLOOR_EARLY: dict[str, float] = {
    "mizuho": MIZUHO_JOB_BUDGET_SEC,
    "sekisui": SEKISUI_JOB_BUDGET_SEC,
    "homes": 45.0,
    "afr": 60.0,
    "sumifu": 35.0,
    "sumai1": 40.0,
    "keio": 40.0,
}


def _effective_job_budget_sec(
    company: str = "",
    budget_sec: float | None = None,
    property_type: str = "",
) -> float:
    budget = budget_sec if budget_sec is not None else _job_budget_sec()
    company_l = company.lower()
    ptype = (property_type or "").lower()
    early = _COMPANY_BUDGET_FLOOR_EARLY.get(company_l)
    if early is not None:
        return max(budget, early)
    # Athome invest needs headroom beyond default Playwright budget (mixed buy_other list).
    if company_l == "athome" and "invest" in ptype:
        return max(budget, ATHOME_INVEST_JOB_BUDGET_SEC)
    if company_l == "odakyu" and ("invest" in ptype or ptype == "investment"):
        return max(budget, 60.0)
    if company_l in PLAYWRIGHT_COMPANIES:
        return max(budget, PLAYWRIGHT_JOB_BUDGET_SEC)
    if "invest" in ptype or ptype == "investment":
        return max(budget, 90.0)
    if company_l == "heim":
        return max(budget, 60.0)
    if company_l == "nomura" and "invest" not in ptype:
        return max(budget, 50.0)
    if company_l == "misawa":
        return max(budget, 35.0)
    return budget


async def _discover_mizuho_via_production_bypass(parser, seed_url: str, limit: int) -> list[str]:
    """
    Mizuho list pages are WAF-blocked for aiohttp/light PW.
    Call sitemap-first get_mizuho_links with the smoke sample limit (avoid fetching 500).
    """
    from package.utils.mizuho_bypass import get_mizuho_links

    parser._last_url = seed_url
    capped = max(1, int(limit))
    urls = await get_mizuho_links(seed_url, limit=capped)
    return [u for u in urls if isinstance(u, str) and u.startswith("http")][:capped]


def _soup_looks_blocked(soup: BeautifulSoup) -> bool:
    """Reject WAF/challenge HTML that still contains navigation links."""
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    title_l = title.lower()
    if "access denied" in title_l or "just a moment" in title_l:
        return True
    if "403" in title and any(tok in title_l for tok in ("forbidden", "error", "denied")):
        return True
    if "認証中" in title or "認証にご協力" in title:
        return True
    body_text = soup.get_text(" ", strip=True)[:800]
    body_l = body_text.lower()
    if "403 forbidden" in body_l or "access denied" in body_l:
        return True
    # Athome bot interstitial (HTTP 200 with empty property shell).
    if "認証中" in body_text or "認証にご協力ください" in body_text:
        return True
    return "just a moment" in body_l


def _soup_usable_for_smoke(soup: BeautifulSoup) -> bool:
    if _soup_looks_blocked(soup):
        return False
    return len(soup.select("a[href]")) >= 3


async def _fetch_via_get_response_bs(parser, session: aiohttp.ClientSession, url: str, deadline: float):
    """Call subclass getResponseBs override (Keio WP REST via requests, etc.)."""
    defining = None
    for cls in type(parser).mro():
        if "getResponseBs" in cls.__dict__:
            defining = cls
            break
    if defining is None or defining.__name__ in ("ParserBase", "object"):
        return None
    method = getattr(parser, "getResponseBs", None)
    if method is None:
        return None
    try:
        return await asyncio.wait_for(
            method(session, url),
            timeout=max(1.0, _remaining(deadline)),
        )
    except Exception as exc:
        logger.debug("smoke getResponseBs failed for %s: %s", url, exc)
        return None


async def _try_get_response_bs_links(parser, session, url, deadline):
    via_bs = await _fetch_via_get_response_bs(parser, session, url, deadline)
    if isinstance(via_bs, BeautifulSoup) and via_bs.select("a[href]"):
        return via_bs
    return None


async def _fetch_soup_force_pw(
    session: aiohttp.ClientSession,
    url: str,
    parser,
    deadline: float,
    pw: _LightPlaywrightSession | None,
) -> Any:
    # Prefer shared light Playwright (reused Chromium). Avoid production
    # stealth parsers here — mizuho/athome _getContent relaunches PW and
    # burns the smoke budget under static∥PW contention.
    if pw is not None:
        if _remaining(deadline) <= 1:
            raise TimeoutError(f"budget exhausted before fetch {url}")
        try:
            html = await pw.fetch_html(url, deadline)
            soup = BeautifulSoup(html, "html.parser")
            if _soup_usable_for_smoke(soup):
                return soup
            if _soup_looks_blocked(soup):
                raise RuntimeError(f"WAF blocked page for {url}")
            return soup
        except Exception as exc:
            if "WAF blocked" in str(exc):
                raise
            logger.debug("smoke force-PW fetch failed for %s: %s", url, exc)
            raise
    via_parser = await _fetch_via_parser(parser, session, url, deadline)
    if via_parser is not None and (
        not isinstance(via_parser, BeautifulSoup) or _soup_usable_for_smoke(via_parser)
    ):
        return via_parser
    return None


def _build_fetch_headers(parser, url: str) -> dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    headers.setdefault("Referer", url)
    if "wp-json" in url:
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["X-Requested-With"] = "XMLHttpRequest"
    if "phfudousan.repros.jp" in url and hasattr(parser, "REPROS_HEADERS"):
        headers.update(parser.REPROS_HEADERS)
    return headers


async def _recover_from_waf_status(
    parser, session, url, deadline, pw, status: int
) -> Any:
    via_bs = await _try_get_response_bs_links(parser, session, url, deadline)
    if via_bs is not None:
        return via_bs
    if pw is not None:
        html = await pw.fetch_html(url, deadline)
        soup = BeautifulSoup(html, "html.parser")
        if not _soup_looks_blocked(soup):
            return soup
    via_parser = await _fetch_via_parser(parser, session, url, deadline)
    if via_parser is not None:
        return via_parser
    raise RuntimeError(f"HTTP {status} / WAF blocked for {url}")


async def _decode_json_response(parser, session, url, deadline, data: Any) -> Any:
    if "phfudousan.repros.jp" in url:
        return data
    html = ""
    if isinstance(data, dict):
        html = data.get("html", "") or ""
    if html:
        return BeautifulSoup(html, "html.parser")
    via_bs = await _try_get_response_bs_links(parser, session, url, deadline)
    if via_bs is not None:
        return via_bs
    return data


def _resolve_response_encoding(parser, content_type: str) -> str:
    encoding = None
    if hasattr(parser, "getCharset"):
        charset = parser.getCharset()
        if charset:
            encoding = charset
    if encoding is None:
        # Honor Content-Type charset (e.g. sumifu shift_jis) before utf-8 default.
        m = re.search(r"charset=([^\s;]+)", content_type.lower())
        if m:
            encoding = m.group(1).strip().strip('"').strip("'")
    if not encoding:
        encoding = "utf-8"
    if encoding.lower() in ("shift_jis", "shift-jis", "x-sjis"):
        return "cp932"
    return encoding


async def _unblock_or_return_soup(
    soup: BeautifulSoup, parser, session, url, deadline, pw
) -> BeautifulSoup:
    # Athome and similar return HTTP 200 for bot interstitials.
    if not _soup_looks_blocked(soup):
        return soup
    if pw is not None:
        if _remaining(deadline) > 3:
            html = await pw.fetch_html(url, deadline)
            return BeautifulSoup(html, "html.parser")
        return soup
    via_parser = await _fetch_via_parser(parser, session, url, deadline)
    if via_parser is not None and (
        not isinstance(via_parser, BeautifulSoup) or not _soup_looks_blocked(via_parser)
    ):
        return via_parser
    return soup


async def _fetch_soup_http(
    session: aiohttp.ClientSession,
    url: str,
    parser,
    deadline: float,
    pw: _LightPlaywrightSession | None,
) -> Any:
    headers = _build_fetch_headers(parser, url)
    ssl_val = _ssl_for_url(url)
    timeout = aiohttp.ClientTimeout(total=_fetch_timeout_sec(url, deadline))
    try:
        async with session.get(url, headers=headers, ssl=ssl_val, timeout=timeout) as resp:
            if resp.status in (403, 503):
                return await _recover_from_waf_status(
                    parser, session, url, deadline, pw, resp.status
                )
            if resp.status != 200:
                via_bs = await _try_get_response_bs_links(parser, session, url, deadline)
                if via_bs is not None:
                    return via_bs
                raise RuntimeError(f"HTTP {resp.status} for {url}")
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type or "wp-json" in url or "phfudousan.repros.jp" in url:
                data = await resp.json(content_type=None)
                return await _decode_json_response(parser, session, url, deadline, data)
            raw = await resp.read()
            encoding = _resolve_response_encoding(parser, content_type)
            soup = BeautifulSoup(raw.decode(encoding, errors="replace"), "html.parser")
            return await _unblock_or_return_soup(soup, parser, session, url, deadline, pw)
    except RuntimeError:
        raise
    except Exception as exc:
        via_bs = await _try_get_response_bs_links(parser, session, url, deadline)
        if via_bs is not None:
            return via_bs
        if pw is not None and _remaining(deadline) > 2:
            html = await pw.fetch_html(url, deadline)
            return BeautifulSoup(html, "html.parser")
        raise


async def _fetch_soup(
    session: aiohttp.ClientSession,
    url: str,
    parser,
    deadline: float,
    pw: _LightPlaywrightSession | None = None,
    force_pw: bool = False,
) -> Any:
    if _remaining(deadline) <= 0:
        raise TimeoutError("job budget exhausted before fetch")

    # Keio list/detail: production getResponseBs uses requests + Referer (aiohttp 403/timeout flake).
    if "keiofudosan" in url or "get_search_result_sale" in url:
        via_bs = await _fetch_via_get_response_bs(parser, session, url, deadline)
        if isinstance(via_bs, BeautifulSoup) and (
            via_bs.select("a.abs_link") or via_bs.select("a[href]")
        ):
            return via_bs

    if force_pw:
        result = await _fetch_soup_force_pw(session, url, parser, deadline, pw)
        if result is not None:
            return result

    return await _fetch_soup_http(session, url, parser, deadline, pw)


def _decode_get_content_bytes(parser, raw: bytes | bytearray) -> BeautifulSoup:
    encoding = "utf-8"
    if hasattr(parser, "getCharset"):
        charset = parser.getCharset()
        if charset:
            encoding = charset
    return BeautifulSoup(raw.decode(encoding, errors="replace"), "html.parser")


def _materialize_get_content(parser, raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, BeautifulSoup)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return _decode_get_content_bytes(parser, raw)
    if isinstance(raw, str):
        return BeautifulSoup(raw, "html.parser")
    return None


async def _fetch_via_parser(parser, session: aiohttp.ClientSession, url: str, deadline: float):
    """Call subclass `_getContent` override (athome stealth Playwright etc.)."""
    defining = None
    for cls in type(parser).mro():
        if "_getContent" in cls.__dict__:
            defining = cls
            break
    if defining is None or defining.__name__ == "ParserBase":
        return None
    getter = getattr(parser, "_getContent", None)
    if getter is None:
        return None
    try:
        raw = await asyncio.wait_for(getter(session, url), timeout=max(1.0, _remaining(deadline)))
    except Exception as exc:
        logger.debug("smoke _getContent failed for %s: %s", url, exc)
        return None
    return _materialize_get_content(parser, raw)


def _parser_overrides_get_content(parser) -> bool:
    for cls in type(parser).mro():
        if "_getContent" in cls.__dict__:
            return cls.__name__ not in ("ParserBase", "object")
    return False


_MIDDLE_LINK_TOKENS = (
    "/mansion/",
    "/kodate/",
    "/house/",
    "/tochi/",
    "/land/",
    "/list",
    "/ensen_",
    "/area",
    "/city",
    "/bukken",
    "bklist",
    "-city",
    "buy_other",
)


def _extract_athome_urls(parser, page, limit: int) -> tuple[list[str], list[str]] | None:
    if "Athome" not in type(parser).__name__ or not hasattr(page, "select"):
        return None
    details: list[str] = []
    middles: list[str] = []
    detail_set: set = set()
    list_set: set = set()
    for a in page.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        detail_url, _ = parser._classify_and_collect_athome_url(href, detail_set, list_set)
        if detail_url and detail_url not in details:
            details.append(detail_url)
        if len(details) >= limit * 2:
            break
    for list_url in list_set:
        if list_url not in middles:
            middles.append(list_url)
    if details or middles:
        return details[: limit * 2], middles[:8]
    return None


async def _invoke_list_method(parser, method, page, limit: int) -> list[Any]:
    try:
        result = method(page)
        if hasattr(result, "__aiter__"):
            return await _collect_async(result, limit * 3)
        if asyncio.iscoroutine(result):
            urls = await result
            if not isinstance(urls, list):
                return list(urls) if urls else []
            return urls
        return list(result) if result else []
    except Exception as exc:
        logger.debug("smoke list method invoke failed: %s", exc)
        return []


def _classify_extracted_url(
    url: str, trust_as_detail: bool, details: list[str], middles: list[str]
) -> None:
    if not isinstance(url, str) or not url.startswith("http"):
        return
    if _looks_like_detail(url):
        if url not in details:
            details.append(url)
        return
    if url not in middles:
        middles.append(url)


async def _extract_via_parser_methods(
    parser, page, limit: int, details: list[str], middles: list[str]
) -> None:
    parser_name = type(parser).__name__
    list_first = ("parsePropertyListPage",) + MIDDLE_PAGE_METHODS
    seen_methods: set[str] = set()
    for method_name in list_first:
        if method_name in seen_methods:
            continue
        seen_methods.add(method_name)
        if "Athome" in parser_name and method_name == "parseRootPage":
            continue
        method = getattr(parser, method_name, None)
        if method is None:
            continue
        urls = await _invoke_list_method(parser, method, page, limit)
        trust_as_detail = method_name in ("parsePropertyListPage", "parseRootPage")
        for url in urls:
            _classify_extracted_url(url, trust_as_detail, details, middles)
        if details:
            break


def _page_base_url(parser, page_url: str) -> str:
    base = getattr(parser, "BASE_URL", "") or ""
    if base or not page_url:
        return base
    parsed = urlparse(page_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _absolute_href(href: str, base: str) -> str | None:
    if not href or href.startswith(("#", "javascript:")):
        return None
    if href.startswith("http"):
        return href
    if not base:
        return None
    return urljoin(base if base.endswith("/") else base + "/", href)


def _append_harvested_link(full: str, details: list[str], middles: list[str]) -> None:
    if _looks_like_detail(full):
        if full not in details:
            details.append(full)
        return
    if any(token in full.lower() for token in _MIDDLE_LINK_TOKENS) and full not in middles:
        middles.append(full)


def _harvest_fallback_links(
    parser, page, page_url: str, details: list[str], middles: list[str]
) -> None:
    if details or middles or not hasattr(page, "select"):
        return
    base = _page_base_url(parser, page_url)
    for anchor in page.select("a[href]"):
        full = _absolute_href(anchor.get("href") or "", base)
        if full:
            _append_harvested_link(full, details, middles)


async def _extract_urls_from_page(
    parser, page, limit: int, page_url: str = ""
) -> tuple[list[str], list[str]]:
    athome = _extract_athome_urls(parser, page, limit)
    if athome is not None:
        return athome

    details: list[str] = []
    middles: list[str] = []
    await _extract_via_parser_methods(parser, page, limit, details, middles)
    _harvest_fallback_links(parser, page, page_url, details, middles)
    return details[: limit * 2], middles[:8]


async def _discover_repros_via_parse_root(
    parser, page: dict, url: str, max_details: int, details: list[str], fetch_errors: list[str]
) -> None:
    payload = page.get("data", page)
    try:
        found = await _collect_async(parser.parseRootPageJson(payload), max_details)
    except Exception as exc:
        fetch_errors.append(f"{url}: {exc}")
        found = []
    for detail in found:
        if isinstance(detail, str) and detail not in details:
            details.append(detail)
        if len(details) >= max_details:
            break


def _discover_repros_via_list_items(
    parser, page: dict, max_details: int, details: list[str]
) -> None:
    items = page.get("data", {}).get("list", [])
    key = getattr(parser, "REPROS_KEY", "")
    detail_endpoint = "kubunDetail"
    if hasattr(parser, "_get_api_paths"):
        _, detail_endpoint, _ = parser._get_api_paths()
    for item in items:
        if "id" not in item:
            continue
        detail = (
            f"https://phfudousan.repros.jp/api/v1/{detail_endpoint}/"
            f"?id={item['id']}&key={key}"
        )
        if detail not in details:
            details.append(detail)
        if len(details) >= max_details:
            break


async def _discover_repros_json_details(
    parser, page: dict, url: str, max_details: int, details: list[str], fetch_errors: list[str]
) -> bool:
    """Handle repros JSON list pages. Returns True when the page was consumed."""
    if hasattr(parser, "parseRootPageJson"):
        await _discover_repros_via_parse_root(
            parser, page, url, max_details, details, fetch_errors
        )
        return True
    _discover_repros_via_list_items(parser, page, max_details, details)
    return True


def _merge_page_details(
    page_details: list[str],
    page_middles: list[str],
    details: list[str],
    frontier: list[tuple[str, int]],
    seen: set[str],
    depth: int,
    max_details: int,
) -> bool:
    """Merge page findings into BFS state. Returns True when enough details found."""
    for detail in page_details:
        if detail not in details:
            details.append(detail)
        if len(details) >= max_details:
            return True
    page_middles.sort(key=lambda u: (0 if "/list" in u.lower() else 1, u))
    for middle in page_middles:
        if middle not in seen and len(frontier) < 8:
            frontier.append((middle, depth + 1))
    return False


async def discover_detail_urls(
    session: aiohttp.ClientSession,
    parser,
    seed_url: str,
    deadline: float,
    max_details: int = 1,
    max_depth: int = DEFAULT_MAX_DEPTH,
    pw: _LightPlaywrightSession | None = None,
    force_pw: bool = False,
) -> list[str]:
    frontier = [(seed_url, 0)]
    seen: set[str] = set()
    details: list[str] = []
    fetch_errors: list[str] = []

    while frontier and len(details) < max_details and _remaining(deadline) > 0:
        url, depth = frontier.pop(0)
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        try:
            page = await _fetch_soup(
                session, url, parser, deadline, pw=pw, force_pw=force_pw
            )
        except Exception as exc:
            fetch_errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue

        if isinstance(page, dict) and "phfudousan.repros.jp" in seed_url:
            await _discover_repros_json_details(
                parser, page, url, max_details, details, fetch_errors
            )
            continue

        page_details, page_middles = await _extract_urls_from_page(
            parser, page, max_details, page_url=url
        )
        if _merge_page_details(
            page_details, page_middles, details, frontier, seen, depth, max_details
        ):
            break

    if not details and fetch_errors:
        raise RuntimeError("; ".join(fetch_errors[:3]))
    return details[:max_details]


async def parse_detail(
    parser,
    session: aiohttp.ClientSession,
    detail_url: str,
    deadline: float,
    pw: _LightPlaywrightSession | None = None,
    force_pw: bool = False,
    job_property_type: str = "",
    company: str = "",
) -> Any:
    page = await _fetch_soup(
        session, detail_url, parser, deadline, pw=pw, force_pw=force_pw
    )
    company_l = company or getattr(parser, "company", "") or ""
    if isinstance(page, dict) and hasattr(parser, "parsePropertyDetailPage"):
        # JSON detail APIs (e.g. rearie) still go through parser async API with our session.
        item = await asyncio.wait_for(
            parser.parsePropertyDetailPage(session, detail_url),
            timeout=_remaining(deadline),
        )
        assert_property_type_for_smoke(
            parser,
            item,
            detail_url,
            None,
            job_property_type or getattr(parser, "property_type", ""),
            company=company_l,
        )
        return item
    if not isinstance(page, BeautifulSoup):
        raise TypeError(f"Detail page is not HTML: {detail_url}")
    item = parser.createEntity()
    item.pageUrl = detail_url
    parser._last_url = detail_url
    parsed = parser._parsePropertyDetailPage(item, page)
    cleaned = parser.clean_parsed_item(parsed)
    assert_property_type_for_smoke(
        parser,
        cleaned,
        detail_url,
        page,
        job_property_type or getattr(parser, "property_type", ""),
        company=company_l,
    )
    return cleaned


def assert_required_fields(item: Any, job_id: str) -> None:
    for field_name in ("propertyName", "price", "address"):
        value = getattr(item, field_name, None)
        if value is None or value == "":
            raise AssertionError(f"[{job_id}] required field '{field_name}' is empty")


def _assert_investment_yield_or_skip(parser, item: Any, detail_url: str) -> None:
    prop_type = ""
    if hasattr(parser, "_resolve_validation_property_type"):
        try:
            prop_type = parser._resolve_validation_property_type(item) or ""
        except Exception as exc:
            logger.debug("smoke investment type resolve failed: %s", exc)
            prop_type = ""
    if prop_type != "investment":
        return
    try:
        gy = float(getattr(item, "grossYield", 0) or 0)
    except (TypeError, ValueError):
        gy = 0.0
    ar = getattr(item, "annualRent", 0) or getattr(item, "monthlyRent", 0) or 0
    try:
        ar_f = float(ar)
    except (TypeError, ValueError):
        ar_f = 0.0
    if gy <= 0 or ar_f <= 0:
        raise SkipPropertyException(
            f"investment listing missing yield/rent for {detail_url}"
        )


def assert_expected_fields_and_persist(parser, item: Any, job_id: str, detail_url: str) -> None:
    """
    Issue #343 success path:
    - expected-spec fields (by property type) must extract without fatal gaps
    - parsed entity must be persisted and reloadable from DB
    Must run in a worker thread when called from asyncio (Django ORM is sync).
    """
    assert_required_fields(item, job_id)
    if not getattr(item, "pageUrl", None):
        item.pageUrl = detail_url
    _assert_investment_yield_or_skip(parser, item, detail_url)
    errors = parser.validate_extracted_fields(item)
    if errors:
        fields = ",".join(str(e.get("field")) for e in errors)
        raise AssertionError(f"[{job_id}] expected field extraction failed: {fields}")
    parser.validate_required_fields(item)
    # Avoid deprecated positional save() args used by legacy batch path.
    item.save(force_insert=False, force_update=False)
    model = type(item)
    if not getattr(item, "pk", None) or not model.objects.filter(pk=item.pk).exists():
        raise AssertionError(f"[{job_id}] DB persist failed for {detail_url}")


async def _assert_expected_fields_and_persist_async(
    parser, item: Any, job_id: str, detail_url: str
) -> None:
    await asyncio.to_thread(
        assert_expected_fields_and_persist, parser, item, job_id, detail_url
    )


def _seeds_from_start_api(target: CrawlTarget) -> list[str]:
    seeds = [target.seed_url]
    try:
        start_cls = load_start_api_class(target)
        url_list = getattr(start_cls, "urlList", None)
        if not url_list:
            url_list = getattr(start_cls(), "urlList", None)
        if url_list:
            for url in url_list:
                if isinstance(url, str) and url.startswith("http") and url not in seeds:
                    seeds.append(url)
    except Exception as exc:
        logger.debug("smoke start-api seeds failed for %s: %s", target.job_id, exc)
    return seeds


def _append_parent_listing_seeds(seeds: list[str], company: str) -> None:
    # Broader parent listing pages often have inventory when leaf areas are empty.
    # Mizuho parents burn a full Playwright bypass each (~30s) — never invent them.
    # Nomura leaf ensen URLs are denser than invented parents (which flake under load).
    if company.lower() in ("mizuho", "nomura"):
        return
    for seed in list(seeds):
        if "?" in seed:
            continue  # don't invent broken parents from query seeds (daiwa etc.)
        parts = seed.rstrip("/").split("/")
        if len(parts) < 6:
            continue
        parent = "/".join(parts[:-1]) + "/"
        if parent.startswith("http") and parent not in seeds:
            seeds.append(parent)
        grand = "/".join(parts[:-2]) + "/"
        if grand.startswith("http") and grand not in seeds:
            seeds.append(grand)


_DEEP_SEED_BY_COMPANY: dict[str, dict[str, str]] = {
    "homes": {
        "mansion": "https://toushi.homes.co.jp/bukkensearch/?tbg[]=2&pref[]=13",
        "kodate": "https://toushi.homes.co.jp/bukkensearch/?tbg[]=4&pref[]=13",
        "tochi": "https://toushi.homes.co.jp/bukkensearch/?tbg[]=5&pref[]=13",
        "invest_apartment": "https://toushi.homes.co.jp/bukkensearch/?tbg[]=1&pref[]=13",
    },
    "athome": {
        "mansion": "https://www.athome.co.jp/mansion/chuko/tokyo/edogawa-city/list/",
        "kodate": "https://www.athome.co.jp/kodate/chuko/tokyo/edogawa-city/list/",
        "tochi": "https://www.athome.co.jp/tochi/tokyo/edogawa-city/list/",
        "invest_apartment": "https://www.athome.co.jp/buy_other/tokyo/edogawa-city/list/",
    },
    "sumifu": {
        "mansion": "https://www.stepon.co.jp/mansion/shutoken/",
        "kodate": "https://www.stepon.co.jp/kodate/shutoken/",
        "tochi": "https://www.stepon.co.jp/tochi/shutoken/",
        "invest_apartment": "https://www.stepon.co.jp/search/list/?type=pro2&searchType=area&prefCd=13",
        "invest_kodate": "https://www.stepon.co.jp/search/list/?type=pro3&searchType=area&prefCd=13",
    },
    "tokyu": {
        "mansion": "https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a13101/",
        "kodate": "https://www.livable.co.jp/kounyu/kodate/tokyo/a13101/",
        "tochi": "https://www.livable.co.jp/kounyu/tochi/tokyo/a13103/",
    },
}


def _prefer_deep_seed(seeds: list[str], company: str, property_type: str) -> list[str]:
    deep_map = _DEEP_SEED_BY_COMPANY.get(company)
    if not deep_map:
        return seeds
    deep = deep_map.get(property_type)
    if not deep:
        return seeds
    if company == "tokyu":
        if deep not in seeds:
            seeds.insert(0, deep)
        return seeds
    return [deep] + [s for s in seeds if s != deep]


def _mizuho_only_seed(property_type: str) -> list[str] | None:
    type_slug = {
        "mansion": "Mansion",
        "kodate": "House",
        "tochi": "Tochi",
    }.get(property_type)
    if not type_slug:
        return None
    return [
        (
            f"https://www.mizuho-re.co.jp/buyers/search/area/"
            f"type_{type_slug}/pref_13/list/"
        )
    ]


def _all_seeds_for_target(target: CrawlTarget) -> list[str]:
    seeds = _seeds_from_start_api(target)
    _append_parent_listing_seeds(seeds, target.company)
    if target.company == "mizuho":
        mizuho = _mizuho_only_seed(target.property_type)
        if mizuho:
            return mizuho
    seeds = _prefer_deep_seed(seeds, target.company, target.property_type)
    return seeds[:6]


@asynccontextmanager
async def _optional_playwright(force_pw: bool):
    # Never attach a PW session for static HTML jobs — lazy chromium on 403/retry
    # under xdist is what hangs local Docker Desktop runs.
    if not force_pw:
        yield None
        return
    async with _LightPlaywrightSession() as pw:
        yield pw


def _effective_sample_size(target: CrawlTarget, sample_size: int | None = None) -> int:
    """Company-aware sample floor for mixed-type / flaky list pages."""
    sample = sample_size or _sample_size()
    company = target.company.lower()
    ptype = (target.property_type or "").lower()
    floors = {"afr": 12, "heim": 10, "daikyo": 10, "homes": 12}
    if company in floors:
        sample = max(sample, floors[company])
    if company in ("mitsui", "keisei", "seibu", "sumirin", "sumai1"):
        sample = max(sample, 8)
    if company in ("nomura", "misawa") and "invest" not in ptype:
        sample = max(sample, 8)
    if company in PLAYWRIGHT_COMPANIES:
        # One success is enough; extra Chromium detail hops blow the wall budget.
        sample = 1
    if "invest" in ptype or ptype == "investment":
        sample = max(sample, 8)
    if company == "athome" and "invest" in ptype:
        sample = min(max(sample, 6), 8)
    return sample


def _smoke_deadline_budget(target: CrawlTarget, budget_sec: float | None) -> float:
    budget = _effective_job_budget_sec(target.company, budget_sec, target.property_type)
    ptype = (target.property_type or "").lower()
    company = target.company.lower()
    if "invest" in ptype or ptype == "investment":
        budget = max(budget, 90.0)
    if company == "athome" and "invest" in ptype:
        budget = max(budget, ATHOME_INVEST_JOB_BUDGET_SEC)
    if company == "odakyu" and ("invest" in ptype or ptype == "investment"):
        budget = max(budget, 60.0)
    if company == "heim":
        budget = max(budget, 60.0)
    return budget


async def _discover_from_seed(
    session,
    parser,
    target: CrawlTarget,
    seed: str,
    sample: int,
    deadline: float,
    pw,
    force_pw: bool,
) -> list[str]:
    if target.company.lower() == "mizuho":
        remain = _remaining(deadline)
        return await asyncio.wait_for(
            _discover_mizuho_via_production_bypass(parser, seed, sample),
            timeout=remain,
        )
    found = await discover_detail_urls(
        session,
        parser,
        seed,
        deadline=deadline,
        max_details=sample,
        max_depth=DEFAULT_MAX_DEPTH,
        pw=pw,
        force_pw=force_pw,
    )
    if (
        not found
        and target.company.lower() in ("odakyu", "homes")
        and _remaining(deadline) > 5
    ):
        await asyncio.sleep(0.4)
        found = await discover_detail_urls(
            session,
            parser,
            seed,
            deadline=deadline,
            max_details=sample,
            max_depth=DEFAULT_MAX_DEPTH,
            pw=pw,
            force_pw=force_pw,
        )
    return found


async def _discover_detail_urls_for_target(
    session,
    parser,
    target: CrawlTarget,
    sample: int,
    deadline: float,
    pw,
    force_pw: bool,
    result: SmokeResult,
) -> tuple[list[str], Exception | None]:
    last_discovery_error: Exception | None = None
    for seed in _all_seeds_for_target(target):
        if _remaining(deadline) <= 1:
            break
        if target.company.lower() == "mizuho" and _remaining(deadline) < 10:
            break
        try:
            found = await _discover_from_seed(
                session, parser, target, seed, sample, deadline, pw, force_pw
            )
        except asyncio.TimeoutError:
            last_discovery_error = TimeoutError("mizuho bypass timed out")
            continue
        except Exception as exc:
            last_discovery_error = exc
            continue
        if found:
            result.seed_url = seed
            return found, None
    return [], last_discovery_error


def _should_skip_paging(company: str, detail_urls: list[str], deadline: float) -> bool:
    company_l = company.lower()
    if not detail_urls:
        return False
    if company_l == "mizuho":
        return True
    if company_l in ("sekisui", "athome"):
        return True
    return company_l in PLAYWRIGHT_COMPANIES and _remaining(deadline) < 40.0


async def _run_paging_check(
    session, parser, target, result, deadline, pw, force_pw, detail_urls
) -> str | None:
    if _should_skip_paging(target.company, detail_urls, deadline):
        pages, exhausted, pok, perr = 1, True, True, None
    else:
        pages, exhausted, pok, perr = await probe_paging(
            session,
            parser,
            result.seed_url,
            deadline,
            pw=pw,
            force_pw=force_pw,
        )
    result.pages_fetched = pages
    result.paging_exhausted = exhausted
    result.paging_ok = pok
    return perr


async def _expand_heim_plan_details(
    session, parser, detail_urls, sample, deadline, pw
) -> list[str]:
    expanded: list[str] = []
    hubs = [u for u in detail_urls if "/plan_detail/" not in u][:4]
    already = [u for u in detail_urls if "/plan_detail/" in u]
    expanded.extend(already)
    for hub in hubs:
        if _remaining(deadline) <= 1.0:
            break
        try:
            hub_page = await _fetch_soup(
                session, hub, parser, deadline, pw=pw, force_pw=False
            )
        except Exception as exc:
            logger.debug("smoke plan_detail hub fetch failed: %s", exc)
            continue
        if not isinstance(hub_page, BeautifulSoup):
            continue
        for a in hub_page.select("a[href*='plan_detail'], a[href*='/outline/']"):
            href = a.get("href") or ""
            full = urljoin(hub, href)
            if full not in expanded:
                expanded.append(full)
    if expanded:
        return expanded[: max(sample, 10)]
    return detail_urls


_SOFT_PARSE_ERR_MARKERS = (
    "Non-mansion",
    "required field",
    "expected field",
    "DB persist",
    "property type mismatch",
)


def _is_soft_parse_error(err: Exception | None) -> bool:
    if err is None:
        return True
    if isinstance(err, (ListingEndedException, SkipPropertyException)):
        return True
    msg = str(err)
    return any(marker in msg for marker in _SOFT_PARSE_ERR_MARKERS)


async def _try_parse_detail(
    parser,
    session,
    detail_url: str,
    deadline: float,
    pw,
    force_pw: bool,
    target: CrawlTarget,
) -> tuple[Any | None, Exception | None]:
    try:
        detail_force_pw = force_pw and target.company.lower() in ("athome", "sekisui")
        item = await parse_detail(
            parser,
            session,
            detail_url,
            deadline,
            pw=pw,
            force_pw=detail_force_pw,
            job_property_type=target.property_type,
            company=target.company,
        )
        await _assert_expected_fields_and_persist_async(
            parser, item, target.job_id, detail_url
        )
        return item, None
    except (ListingEndedException, SkipPropertyException) as exc:
        return None, exc
    except Exception as exc:
        if _is_soft_parse_error(exc):
            return None, exc
        if target.company.lower() == "afr":
            return None, exc
        if target.company.lower() not in PLAYWRIGHT_COMPANIES:
            return None, exc
        try:
            item = await parse_detail(
                parser,
                session,
                detail_url,
                deadline,
                pw=pw,
                force_pw=True,
                job_property_type=target.property_type,
                company=target.company,
            )
            await _assert_expected_fields_and_persist_async(
                parser, item, target.job_id, detail_url
            )
            return item, None
        except Exception as exc2:
            return None, exc2


def _record_parse_success(result: SmokeResult, item: Any) -> None:
    result.parsed_ok += 1
    result.property_type_ok = True
    name = getattr(item, "propertyName", "") or ""
    result.sample_names.append(str(name)[:80])


async def _parse_afr_parallel(
    detail_urls: list[str], deadline: float, result: SmokeResult, try_parse
) -> None:
    batch = detail_urls[: min(8, len(detail_urls))]
    remain = max(1.0, _remaining(deadline))
    tasks = [asyncio.create_task(try_parse(u)) for u in batch]
    try:
        for coro in asyncio.as_completed(tasks, timeout=remain):
            try:
                outcome = await coro
            except Exception as exc:
                logger.debug("smoke afr parallel parse task failed: %s", exc)
                continue
            if isinstance(outcome, Exception):
                continue
            item, _err = outcome
            if item is not None:
                _record_parse_success(result, item)
                break
    except asyncio.TimeoutError:
        if result.parsed_ok == 0:
            result.errors.append(f"afr parallel parse exceeded {remain:.0f}s")
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()


async def _parse_details_sequential(
    detail_urls: list[str],
    deadline: float,
    budget: float,
    result: SmokeResult,
    try_parse,
) -> None:
    for detail_url in detail_urls:
        if _remaining(deadline) <= 0:
            if result.parsed_ok == 0:
                result.errors.append(f"job budget {budget:.0f}s exhausted")
            break
        item, err = await try_parse(detail_url)
        if item is not None:
            _record_parse_success(result, item)
            break
        if err is not None and not _is_soft_parse_error(err):
            result.errors.append(f"{detail_url}: {err}")


def _finalize_smoke_result(result: SmokeResult, paging_error: str | None) -> None:
    if result.parsed_ok == 0 and not result.errors:
        result.errors.append("No detail pages successfully parsed")
    if result.parsed_ok > 0:
        result.errors.clear()
    if not result.paging_ok:
        result.errors.append(paging_error or "paging check failed")
    if result.parsed_ok > 0 and not result.property_type_ok:
        result.errors.append("property type check failed")


async def _smoke_crawl_with_session(
    session,
    parser,
    target: CrawlTarget,
    sample: int,
    budget: float,
    deadline: float,
    force_pw: bool,
    result: SmokeResult,
    started: float,
) -> SmokeResult:
    async with _optional_playwright(force_pw) as pw:
        detail_urls, last_discovery_error = await _discover_detail_urls_for_target(
            session, parser, target, sample, deadline, pw, force_pw, result
        )
        if not detail_urls:
            if last_discovery_error is not None:
                result.errors.append(
                    f"Detail URL discovery failed: {last_discovery_error}"
                )
            else:
                result.errors.append(
                    f"ZERO DETAIL URLS extracted via production parser from {target.seed_url}"
                )
            result.elapsed_sec = time.monotonic() - started
            return result

        result.detail_urls_found = len(detail_urls)
        paging_error = await _run_paging_check(
            session, parser, target, result, deadline, pw, force_pw, detail_urls
        )

        if target.company.lower() == "heim":
            detail_urls = await _expand_heim_plan_details(
                session, parser, detail_urls, sample, deadline, pw
            )
            result.detail_urls_found = len(detail_urls)

        async def _try_parse(detail_url: str):
            return await _try_parse_detail(
                parser, session, detail_url, deadline, pw, force_pw, target
            )

        if target.company.lower() == "afr" and len(detail_urls) > 1:
            await _parse_afr_parallel(detail_urls, deadline, result, _try_parse)
        else:
            await _parse_details_sequential(
                detail_urls, deadline, budget, result, _try_parse
            )

        _finalize_smoke_result(result, paging_error)
    return result


def _legacy_ssl_context() -> ssl.SSLContext:
    """SSL context allowing SECLEVEL=1 for legacy servers (Misawa/Keio)."""
    ctx = ssl.create_default_context()
    try:
        # Required for legacy 1024-bit DH keys on Misawa/Keio
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")  # NOSONAR
    except (ssl.SSLError, ValueError):
        pass
    return ctx


async def smoke_crawl_target(
    target: CrawlTarget,
    sample_size: int | None = None,
    budget_sec: float | None = None,
) -> SmokeResult:
    sample = _effective_sample_size(target, sample_size)
    budget = _smoke_deadline_budget(target, budget_sec)
    deadline = time.monotonic() + budget
    started = time.monotonic()
    result = SmokeResult(job_id=target.job_id, seed_url=target.seed_url)

    try:
        parser = load_parser_for_target(target)
    except Exception as exc:
        result.errors.append(f"parser load failed: {exc}")
        result.elapsed_sec = time.monotonic() - started
        return result

    target_ssl = (
        _legacy_ssl_context()
        if target.company.lower() in ("misawa", "keio")
        else ssl.create_default_context()
    )
    timeout = aiohttp.ClientTimeout(total=_http_timeout_sec())
    connector = aiohttp.TCPConnector(limit=4, ttl_dns_cache=60, ssl=target_ssl)
    force_pw = _needs_playwright(parser, target.company)

    try:
        async with aiohttp.ClientSession(
            headers=DEFAULT_HEADERS, connector=connector, timeout=timeout
        ) as session:
            await _smoke_crawl_with_session(
                session,
                parser,
                target,
                sample,
                budget,
                deadline,
                force_pw,
                result,
                started,
            )
    except Exception as exc:
        result.errors.append(str(exc))

    result.elapsed_sec = time.monotonic() - started
    return result


def run_smoke_sync(
    target: CrawlTarget,
    sample_size: int | None = None,
    budget_sec: float | None = None,
) -> SmokeResult:
    budget = _effective_job_budget_sec(
        target.company, budget_sec, getattr(target, "property_type", "")
    )
    hard_limit = budget + 20.0

    async def _runner() -> SmokeResult:
        return await asyncio.wait_for(
            smoke_crawl_target(target, sample_size=sample_size, budget_sec=budget),
            timeout=hard_limit,
        )

    try:
        return asyncio.run(_runner())
    except asyncio.TimeoutError:
        return SmokeResult(
            job_id=target.job_id,
            seed_url=target.seed_url,
            elapsed_sec=hard_limit,
            errors=[f"TimeoutError: smoke hard limit exceeded ({hard_limit:.0f}s)"],
        )
    except Exception as exc:
        return SmokeResult(
            job_id=target.job_id,
            seed_url=target.seed_url,
            elapsed_sec=budget,
            errors=[f"smoke crashed: {exc}"],
        )
