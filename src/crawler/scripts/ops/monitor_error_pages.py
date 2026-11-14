# -*- coding: utf-8 -*-
"""Cross-platform and GCS-aware parser error page monitor (Issue #1410)."""
from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

_current_dir = os.path.dirname(os.path.abspath(__file__))
_crawler_dir = os.path.dirname(os.path.dirname(_current_dir))
_project_root = os.path.dirname(os.path.dirname(_crawler_dir))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

log_dir = os.path.join(_project_root, "logs")
os.makedirs(log_dir, exist_ok=True)

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _default_error_dirs() -> list[str]:
    dirs = [os.path.join(_project_root, "docs", "error_pages")]
    runs_dir = Path(_project_root) / "logs" / "runs"
    if runs_dir.exists():
        for p in runs_dir.glob("*/error_pages"):
            if p.is_dir():
                dirs.append(str(p))
    return dirs


ERROR_DIRS = _default_error_dirs()


def parse_meta_text(text: str) -> dict[str, str]:
    info = {"url": "unknown", "reason": "unknown", "timestamp": "unknown"}
    for line in text.splitlines():
        if line.startswith("URL:"):
            info["url"] = line.split("URL:", 1)[1].strip()
        elif line.startswith("Reason:"):
            info["reason"] = line.split("Reason:", 1)[1].strip()
        elif line.startswith("Timestamp:"):
            info["timestamp"] = line.split("Timestamp:", 1)[1].strip()
    return info


def parse_meta_file(meta_path: str | Path) -> dict[str, str]:
    p = Path(meta_path)
    if not p.exists():
        return {"url": "unknown", "reason": "unknown", "timestamp": "unknown"}
    try:
        return parse_meta_text(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to parse meta file %s: %s", meta_path, exc)
        return {"url": "unknown", "reason": "unknown", "timestamp": "unknown"}


def _record_local_html_file(
    html_path: Path,
    cutoff_ts: float,
    now_str: str,
    summary: dict[str, Any],
) -> None:
    company_type = html_path.parent.name or "unknown"
    bucket = summary["by_company_type"].setdefault(company_type, {"total": 0, "recent_24h": 0})
    summary["total_errors"] += 1
    bucket["total"] += 1

    try:
        mtime = html_path.stat().st_mtime
    except OSError:
        return
    if mtime < cutoff_ts:
        return

    meta_path = html_path.with_name(html_path.name.replace(".html", "_meta.txt"))
    meta_info = parse_meta_file(meta_path)
    ts_str = meta_info["timestamp"]
    if ts_str == "unknown":
        ts_str = datetime.datetime.fromtimestamp(mtime).strftime(DATETIME_FORMAT) or now_str

    summary["recent_errors_24h"] += 1
    bucket["recent_24h"] += 1
    summary["recent_details"].append({
        "company_type": company_type,
        "file": html_path.name,
        "url": meta_info["url"],
        "reason": meta_info["reason"],
        "timestamp": ts_str,
    })


def _scan_gcs_error_pages(now_utc: datetime.datetime, summary: dict[str, Any]) -> None:
    try:
        from package.utils.storage import get_storage_manager

        sm = get_storage_manager()
    except Exception as exc:  # noqa: BLE001
        logging.debug("Skipping GCS error page scan: %s", exc)
        return

    date_keys = [
        now_utc.strftime("%Y-%m-%d"),
        (now_utc - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
    ]
    for day_str in date_keys:
        prefix = f"runs/{day_str}/error_pages/"
        keys = sm.list_files(prefix=prefix, raise_on_error=False) or []
        html_keys = [k for k in keys if str(k).endswith(".html")]
        key_set = set(keys)
        for hk in html_keys:
            parts = str(hk).split("/")
            comp_type = parts[-2] if len(parts) >= 2 else "unknown"
            fname = parts[-1]
            bucket = summary["by_company_type"].setdefault(comp_type, {"total": 0, "recent_24h": 0})
            summary["total_errors"] += 1
            summary["recent_errors_24h"] += 1
            bucket["total"] += 1
            bucket["recent_24h"] += 1
            meta_key = str(hk).replace(".html", "_meta.txt")
            meta_info = {"url": "unknown", "reason": "unknown", "timestamp": day_str}
            if meta_key in key_set and len(summary["recent_details"]) < 100:
                try:
                    meta_info = parse_meta_text(sm.read_text(meta_key))
                except Exception:  # noqa: BLE001
                    pass
            summary["recent_details"].append({
                "company_type": comp_type,
                "file": fname,
                "url": meta_info["url"],
                "reason": meta_info["reason"],
                "timestamp": meta_info["timestamp"],
            })


def collect_error_page_summary(
    error_dirs: list[str] | None = None,
    include_gcs: bool | None = None,
) -> dict[str, Any]:
    now = datetime.datetime.now()
    now_str = now.strftime(DATETIME_FORMAT)
    cutoff_ts = now.timestamp() - 86400.0
    summary: dict[str, Any] = {
        "timestamp": now_str,
        "total_errors": 0,
        "recent_errors_24h": 0,
        "by_company_type": {},
        "recent_details": [],
    }

    target_dirs = error_dirs if error_dirs is not None else _default_error_dirs()
    seen_files: set[Path] = set()
    for base_dir in target_dirs:
        base_path = Path(base_dir)
        if not base_path.exists():
            continue
        for html_path in base_path.rglob("*.html"):
            resolved = html_path.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            _record_local_html_file(html_path, cutoff_ts, now_str, summary)

    if include_gcs is None:
        include_gcs = (
            os.getenv("IS_CLOUD", "").strip().lower() in ("1", "true")
            or os.getenv("STORAGE_BACKEND", "").strip().lower() == "gcs"
        ) and not bool(os.getenv("PYTEST_CURRENT_TEST"))

    if include_gcs:
        _scan_gcs_error_pages(datetime.datetime.now(datetime.timezone.utc), summary)

    return summary


def main() -> dict[str, Any]:
    logging.info("Starting monitor_error_pages.py (pathlib + GCS hybrid)...")
    error_summary = collect_error_page_summary()

    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"error_report_{today_str}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(error_summary, f, ensure_ascii=False, indent=2)

    logging.info("Error monitoring finished. Report written to %s", report_path)
    logging.info(
        "Total Errors: %d, Recent (24h): %d",
        error_summary["total_errors"],
        error_summary["recent_errors_24h"],
    )

    alert_threshold = int(os.getenv("ERROR_ALERT_THRESHOLD", "5"))
    if error_summary["recent_errors_24h"] >= alert_threshold:
        logging.warning(
            "⚠️ ALERT: %d parse errors detected in the last 24 hours!",
            error_summary["recent_errors_24h"],
        )
        for detail in error_summary["recent_details"]:
            logging.warning(
                "  - [%s] Reason: %s | URL: %s",
                detail["company_type"],
                detail["reason"],
                detail["url"],
            )
    return error_summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt=DATETIME_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "error_monitor.log"), encoding="utf-8"),
        ],
    )
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    main()
