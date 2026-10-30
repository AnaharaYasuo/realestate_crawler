"""Job metrics tracker and exporter for crawler processes (Issue #952, #1151).

Tracks detail processing count, skipped count, and field fill-rate drift metrics
and exports them to JSON files so that parent orchestrator (run_all_crawlers.py)
can directly collect counts and detect silent schema/DOM degradation.
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
_is_empty_result: bool = False

DEFAULT_MONITORED_FIELDS: tuple[str, ...] = (
    "propertyName",
    "price",
    "address",
    "station1",
    "railway1",
    "railwayWalkMinute1",
)


def _is_field_filled(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val > 0
    return bool(str(val).strip())


def compute_field_fill_rates(
    items: list[Any],
    fields: tuple[str, ...] | None = None,
) -> dict[str, float]:
    """Compute per-field non-null/non-empty fill rates (0.0 to 1.0) across parsed items."""
    target_fields = fields or DEFAULT_MONITORED_FIELDS
    if not items:
        return dict.fromkeys(target_fields, 0.0)

    total = len(items)
    rates: dict[str, float] = {}
    for field in target_fields:
        filled = 0
        for item in items:
            val = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
            if _is_field_filled(val):
                filled += 1
        rates[field] = round(filled / total, 4)
    return rates


def reset_metrics() -> None:
    """Reset process-local metrics counters."""
    global _detail_count, _skipped_count, _is_empty_result
    with _lock:
        _detail_count = 0
        _skipped_count = 0
        _is_empty_result = False


def mark_empty_result() -> None:
    """Mark current job run as a valid empty result (0 active listings on site)."""
    global _is_empty_result
    with _lock:
        _is_empty_result = True


def is_empty_result_marked() -> bool:
    """Check if empty result is marked."""
    with _lock:
        return _is_empty_result


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
    date_str = run_date or datetime.datetime.now(datetime.UTC).date().strftime("%Y%m%d")
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
    is_empty_result: bool | None = None,
    field_fill_rates: dict[str, float] | None = None,
) -> Path | None:
    """
    Export crawler metrics to JSON file atomically.
    If detail_cnt or skipped_cnt is None, reads from local tracker.
    """
    cur_detail, cur_skip = get_current_metrics()
    final_detail = cur_detail if detail_cnt is None else detail_cnt
    final_skip = cur_skip if skipped_cnt is None else skipped_cnt
    final_empty = is_empty_result if is_empty_result is not None else is_empty_result_marked()

    metrics_path = get_metrics_file_path(company, property_type, run_date)
    data: dict[str, Any] = {
        "company": company.lower(),
        "property_type": property_type.lower(),
        "detail_cnt": final_detail,
        "skipped_cnt": final_skip,
        "total_cnt": final_detail + final_skip,
        "is_empty_result": bool(final_empty),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    if field_fill_rates is not None:
        data["field_fill_rates"] = field_fill_rates

    tmp_path = metrics_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(metrics_path)
        logger.info(
            "Saved job metrics for %s - %s: detail=%d, skipped=%d, is_empty_result=%s to %s",
            company, property_type, final_detail, final_skip, final_empty, metrics_path,
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
) -> tuple[int, int, int, bool] | None:
    """
    Read job metrics from JSON file if available.
    Returns: (detail_cnt, skipped_cnt, total_cnt, is_empty_result) or None if file not found / invalid.
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
        is_empty = bool(data.get("is_empty_result", False))
        return detail, skipped, total, is_empty
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to read job metrics from %s: %s",
            metrics_path, e,
        )
        return None
