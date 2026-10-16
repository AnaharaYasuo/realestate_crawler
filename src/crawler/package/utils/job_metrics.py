"""Job metrics tracker and exporter for crawler processes (Issue #952).

Tracks detail processing count, skipped count, and export metrics to JSON files
so that parent orchestrator (run_all_crawlers.py) can directly collect counts
without hammering the database with heavy COUNT(*) queries.
"""
from __future__ import annotations

import datetime
import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_detail_count: int = 0
_skipped_count: int = 0


def reset_metrics() -> None:
    """Reset process-local metrics counters."""
    global _detail_count, _skipped_count
    with _lock:
        _detail_count = 0
        _skipped_count = 0


def record_detail_processed(n: int = 1) -> None:
    """Record successfully processed detail item(s)."""
    global _detail_count
    with _lock:
        _detail_count += n


def record_item_skipped(n: int = 1) -> None:
    """Record skipped item(s) due to unchanged price / cache."""
    global _skipped_count
    with _lock:
        _skipped_count += n


def get_current_metrics() -> tuple[int, int]:
    """Get current (detail_count, skipped_count)."""
    with _lock:
        return _detail_count, _skipped_count


def _get_metrics_dir(run_date: str | None = None) -> Path:
    date_str = run_date or datetime.datetime.now(datetime.timezone.utc).date().strftime("%Y%m%d")
    d = Path("logs/runs") / date_str
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_metrics_file_path(company: str, property_type: str, run_date: str | None = None) -> Path:
    """Get JSON file path for a specific crawler job."""
    c = company.lower()
    p = property_type.lower()
    return _get_metrics_dir(run_date) / f"metrics_{c}_{p}.json"


def export_job_metrics(
    company: str,
    property_type: str,
    detail_cnt: int | None = None,
    skipped_cnt: int | None = None,
    run_date: str | None = None,
) -> Path | None:
    """
    Export crawler metrics to JSON file atomically.
    If detail_cnt or skipped_cnt is None, reads from local tracker.
    """
    cur_detail, cur_skip = get_current_metrics()
    final_detail = cur_detail if detail_cnt is None else detail_cnt
    final_skip = cur_skip if skipped_cnt is None else skipped_cnt

    metrics_path = get_metrics_file_path(company, property_type, run_date)
    data: dict[str, Any] = {
        "company": company.lower(),
        "property_type": property_type.lower(),
        "detail_cnt": final_detail,
        "skipped_cnt": final_skip,
        "total_cnt": final_detail + final_skip,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    tmp_path = metrics_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(metrics_path)
        logger.info(
            "Saved job metrics for %s - %s: detail=%d, skipped=%d to %s",
            company, property_type, final_detail, final_skip, metrics_path,
        )
        return metrics_path
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to export job metrics for %s - %s: %s",
            company, property_type, e,
        )
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return None


def read_job_metrics(
    company: str,
    property_type: str,
    run_date: str | None = None,
) -> tuple[int, int, int] | None:
    """
    Read job metrics from JSON file if available.
    Returns: (detail_cnt, skipped_cnt, total_cnt) or None if file not found / invalid.
    """
    metrics_path = get_metrics_file_path(company, property_type, run_date)
    if not metrics_path.exists():
        return None

    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        detail = int(data.get("detail_cnt", 0))
        skipped = int(data.get("skipped_cnt", 0))
        total = int(data.get("total_cnt", detail + skipped))
        return detail, skipped, total
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to read job metrics from %s: %s",
            metrics_path, e,
        )
        return None
