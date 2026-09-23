# -*- coding: utf-8 -*-
"""Shared crawl job definitions (Single Source of Truth for production + tests)."""

CRAWL_JOBS = [
    # 主要5社 (居住用)
    ("mitsui", "mansion"),
    ("mitsui", "kodate"),
    ("mitsui", "tochi"),
    ("sumifu", "mansion"),
    ("sumifu", "kodate"),
    ("sumifu", "tochi"),
    ("tokyu", "mansion"),
    ("tokyu", "kodate"),
    ("tokyu", "tochi"),
    ("nomura", "mansion"),
    ("nomura", "kodate"),
    ("nomura", "tochi"),
    ("misawa", "mansion"),
    ("misawa", "kodate"),
    ("misawa", "tochi"),
    # 信託・銀行系列3社 (居住用)
    ("smtrc", "mansion"),
    ("smtrc", "kodate"),
    ("smtrc", "tochi"),
    ("sumai1", "mansion"),
    ("sumai1", "kodate"),
    ("sumai1", "tochi"),
    ("mizuho", "mansion"),
    ("mizuho", "kodate"),
    ("mizuho", "tochi"),
    # 電鉄・ハウスメーカー・その他系列 (居住用)
    ("sekisui", "mansion"),
    ("sekisui", "kodate"),
    ("sekisui", "tochi"),
    ("afr", "mansion"),
    ("afr", "kodate"),
    ("afr", "tochi"),
    ("daiwa", "mansion"),
    ("daiwa", "kodate"),
    ("daiwa", "tochi"),
    ("totate", "mansion"),
    ("totate", "kodate"),
    ("totate", "tochi"),
    ("odakyu", "mansion"),
    ("odakyu", "kodate"),
    ("odakyu", "tochi"),
    ("sumirin", "mansion"),
    ("sumirin", "kodate"),
    ("sumirin", "tochi"),
    ("heim", "mansion"),
    ("heim", "kodate"),
    ("heim", "tochi"),
    ("rearie", "mansion"),
    ("rearie", "kodate"),
    ("rearie", "tochi"),
    ("keio", "mansion"),
    ("keio", "kodate"),
    ("keio", "tochi"),
    ("seibu", "mansion"),
    ("seibu", "kodate"),
    ("seibu", "tochi"),
    ("keikyu", "mansion"),
    ("keikyu", "kodate"),
    ("keikyu", "tochi"),
    ("sotetsu", "mansion"),
    ("sotetsu", "kodate"),
    ("sotetsu", "tochi"),
    ("keisei", "mansion"),
    ("keisei", "kodate"),
    ("keisei", "tochi"),
    ("daikyo", "mansion"),
    ("daikyo", "kodate"),
    ("daikyo", "tochi"),
    # ポータルサイト (居住用)
    ("athome", "mansion"),
    ("athome", "kodate"),
    ("athome", "tochi"),
    ("homes", "mansion"),
    ("homes", "kodate"),
    ("homes", "tochi"),
    # 投資用・事業用物件
    ("mitsui", "invest_kodate"),
    ("mitsui", "invest_apartment"),
    ("sumifu", "invest_kodate"),
    ("sumifu", "invest_apartment"),
    ("tokyu", "invest_kodate"),
    ("tokyu", "invest_apartment"),
    ("nomura", "invest_kodate"),
    ("nomura", "invest_apartment"),
    ("misawa", "invest_kodate"),
    ("misawa", "invest_apartment"),
    ("athome", "invest_apartment"),
    ("homes", "invest_apartment"),
    ("smtrc", "investment"),
    ("sumai1", "investment"),
    ("mizuho", "investment"),
    ("odakyu", "investment"),
    ("sumirin", "investment"),
]


def filter_crawl_jobs(
    jobs: list[tuple[str, str]] | None = None,
    *,
    sites: str | None = None,
    company: str | None = None,
    property_type: str | None = None,
) -> list[tuple[str, str]]:
    """
    Narrow CRAWL_JOBS for targeted live verification.

    ``sites`` is a comma-separated list of tokens:
      - company code: ``sumifu`` (all types for that company)
      - job id: ``sumifu_mansion`` / ``odakyu_investment``
      - company:type: ``sumifu:mansion`` or ``sumifu/mansion``

    ``company`` / ``property_type`` further AND-filter (optional TYPE alone is invalid
    without COMPANY — ignored if COMPANY empty).
    Empty filters return the full job list unchanged.
    """
    selected = list(jobs if jobs is not None else CRAWL_JOBS)
    sites_raw = (sites or "").strip()
    company_l = (company or "").strip().lower()
    type_l = (property_type or "").strip().lower()

    if sites_raw:
        tokens = [t.strip() for t in sites_raw.split(",") if t.strip()]
        matched: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        job_ids = {f"{c}_{p}": (c, p) for c, p in selected}
        by_company: dict[str, list[tuple[str, str]]] = {}
        for c, p in selected:
            by_company.setdefault(c.lower(), []).append((c, p))

        for tok in tokens:
            key = tok.lower().replace("-", "_")
            if key in job_ids:
                job = job_ids[key]
                if job not in seen:
                    matched.append(job)
                    seen.add(job)
                continue
            if ":" in tok or "/" in tok:
                sep = ":" if ":" in tok else "/"
                left, _, right = tok.partition(sep)
                c, p = left.strip().lower(), right.strip().lower()
                cand = (c, p)
                # preserve original casing from selected
                for jc, jp in selected:
                    if jc.lower() == c and jp.lower() == p:
                        cand = (jc, jp)
                        break
                else:
                    raise ValueError(f"Unknown crawl job in SITES: {tok!r}")
                if cand not in seen:
                    matched.append(cand)
                    seen.add(cand)
                continue
            if key in by_company:
                for job in by_company[key]:
                    if job not in seen:
                        matched.append(job)
                        seen.add(job)
                continue
            raise ValueError(
                f"Unknown site/job token in SITES: {tok!r}. "
                f"Use company code (e.g. sumifu), job id (sumifu_mansion), "
                f"or company:type (sumifu:mansion)."
            )
        selected = matched

    if company_l:
        selected = [(c, p) for c, p in selected if c.lower() == company_l]
        if type_l:
            selected = [(c, p) for c, p in selected if p.lower() == type_l]
        if not selected:
            raise ValueError(
                f"No CRAWL_JOBS match COMPANY={company!r} TYPE={property_type!r}"
            )
    elif type_l:
        raise ValueError("CRAWL_GUARANTEE_TYPE / TYPE requires COMPANY to be set")

    return selected


def jobs_from_env(
    jobs: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """Apply CRAWL_GUARANTEE_SITES / _COMPANY / _TYPE env filters."""
    import os

    return filter_crawl_jobs(
        jobs,
        sites=os.environ.get("CRAWL_GUARANTEE_SITES"),
        company=os.environ.get("CRAWL_GUARANTEE_COMPANY"),
        property_type=os.environ.get("CRAWL_GUARANTEE_TYPE"),
    )
