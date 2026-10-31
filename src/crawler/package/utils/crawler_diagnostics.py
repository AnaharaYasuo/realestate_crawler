"""Per-thread lock-free diagnostic context and hang/resource snapshot collector.

Design Principles (Issue #1170):
1. Single Responsibility Principle (SRP):
   - Liveness heartbeat (`touch_crawler_progress`) and diagnostic state recording
     are strictly separated. This module NEVER touches `.touch` files.
2. Zero Shared-File Contention Across Threads:
   - Threads NEVER write to a shared file.
   - Each thread updates only its own thread-local slot (`threading.local()`) and,
     when persisted to disk for cross-process visibility, writes exclusively to its
     own per-thread file (`logs/diagnostics/<company>_<ptype>/thread_<tid>.json`).
3. Full Observability on Hang / Failure:
   - Captures active URLs (`current_url`, `parent_list_url`), processing `phase`,
     per-thread Python stack traces (`sys._current_frames()`), asyncio task stacks,
     hardware resources (CPU %, RSS/VMS memory, child processes), network socket
     states (`ESTABLISHED`, `SYN_SENT`, `CLOSE_WAIT`, `TIME_WAIT`), and database
     connection state (Django `connections` + ProxySQL TCP probe).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
from typing import Any

JST = datetime.timezone(datetime.timedelta(hours=9))

_CRAWLER_ROOT = Path(__file__).resolve().parent.parent.parent
DIAGNOSTICS_BASE_DIR = _CRAWLER_ROOT / "logs" / "diagnostics"
THREAD_STATE_GLOB = "thread_*.json"

# Thread-local storage so each thread owns its state without lock contention
_thread_local = threading.local()

# Registry mapping thread_id -> dict reference (each dict is mutated ONLY by its owner thread)
_thread_slots: dict[int, dict[str, Any]] = {}
_active_job_context: dict[str, str] = {"company": "", "property_type": ""}
_THROTTLE_DISK_FLUSH_SEC = 1.0


def set_diagnostic_job_context(company: str, property_type: str) -> Path:
    """Initialize diagnostic directory for a specific job in the current process."""
    _active_job_context["company"] = str(company or "")
    _active_job_context["property_type"] = str(property_type or "")
    job_dir = get_job_diagnostics_dir(company, property_type)
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        cleanup_job_diagnostic_dir(company, property_type)
    except OSError:
        pass
    return job_dir


def get_job_diagnostics_dir(company: str = "", property_type: str = "") -> Path:
    """Return the directory storing per-thread diagnostic files for a job."""
    comp = company or _active_job_context.get("company") or "unknown"
    ptype = property_type or _active_job_context.get("property_type") or "unknown"
    return DIAGNOSTICS_BASE_DIR / f"{comp}_{ptype}"


def _get_job_diag_dir(company: str = "", property_type: str = "") -> Path:
    """Alias for get_job_diagnostics_dir."""
    return get_job_diagnostics_dir(company, property_type)


def cleanup_job_diagnostic_dir(company: str = "", property_type: str = "") -> None:
    """Remove stale per-thread diagnostic files for a job."""
    try:
        job_dir = get_job_diagnostics_dir(company, property_type)
        if not job_dir.exists():
            return
        for old_file in job_dir.glob(THREAD_STATE_GLOB):
            try:
                old_file.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass


def _create_thread_slot(
    tid: int,
    phase: str,
    current_url: str,
    parent_list_url: str,
    company: str,
    property_type: str,
    now_ts: float,
    now_iso: str,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "thread_id": tid,
        "thread_name": threading.current_thread().name,
        "company": company or _active_job_context.get("company", ""),
        "property_type": property_type or _active_job_context.get("property_type", ""),
        "phase": phase,
        "current_url": current_url,
        "parent_list_url": parent_list_url,
        "phase_started_at": now_ts,
        "updated_at": now_ts,
        "updated_iso": now_iso,
        "extra": extra or {},
    }


def _update_existing_thread_slot(
    slot: dict[str, Any],
    phase: str,
    current_url: str,
    parent_list_url: str,
    company: str,
    property_type: str,
    now_ts: float,
    now_iso: str,
    extra: dict[str, Any] | None,
) -> None:
    if slot.get("phase") != phase or (current_url and slot.get("current_url") != current_url):
        slot["phase_started_at"] = now_ts
    slot["thread_name"] = threading.current_thread().name
    slot["company"] = company or slot.get("company") or _active_job_context.get("company", "")
    slot["property_type"] = (
        property_type or slot.get("property_type") or _active_job_context.get("property_type", "")
    )
    slot["phase"] = phase
    if current_url:
        slot["current_url"] = current_url
    if parent_list_url:
        slot["parent_list_url"] = parent_list_url
    slot["updated_at"] = now_ts
    slot["updated_iso"] = now_iso
    if extra is not None:
        slot["extra"] = extra


def record_thread_activity(
    phase: str,
    current_url: str = "",
    parent_list_url: str = "",
    *,
    company: str = "",
    property_type: str = "",
    extra: dict[str, Any] | None = None,
    force_flush: bool = False,
) -> None:
    """Update the calling thread's own diagnostic state without shared file locking."""
    tid = threading.get_ident()
    now_ts = time.time()
    now_iso = datetime.datetime.now(JST).isoformat()

    slot: dict[str, Any] | None = getattr(_thread_local, "slot", None)
    if slot is None or slot.get("thread_id") != tid:
        slot = _create_thread_slot(
            tid, phase, current_url, parent_list_url, company, property_type, now_ts, now_iso, extra
        )
        _thread_local.slot = slot
        _thread_local.last_flush_ts = 0.0
        _thread_slots[tid] = slot
    else:
        _update_existing_thread_slot(
            slot, phase, current_url, parent_list_url, company, property_type, now_ts, now_iso, extra
        )

    last_flush = getattr(_thread_local, "last_flush_ts", 0.0)
    if force_flush or (now_ts - last_flush) >= _THROTTLE_DISK_FLUSH_SEC:
        _flush_thread_slot_to_disk(tid, slot)
        _thread_local.last_flush_ts = now_ts


def clear_thread_activity(phase: str = "idle") -> None:
    """Mark the calling thread as idle (e.g., when a worker finishes an item)."""
    tid = threading.get_ident()
    now_ts = time.time()
    slot: dict[str, Any] | None = getattr(_thread_local, "slot", None)
    if slot is not None:
        slot["phase"] = phase
        slot["updated_at"] = now_ts
        slot["updated_iso"] = datetime.datetime.now(JST).isoformat()
        _flush_thread_slot_to_disk(tid, slot)
        _thread_local.last_flush_ts = now_ts


def _flush_thread_slot_to_disk(tid: int, slot: dict[str, Any]) -> None:
    """Write the calling thread's state to its dedicated `thread_<tid>.json` file."""
    comp = slot.get("company") or _active_job_context.get("company")
    ptype = slot.get("property_type") or _active_job_context.get("property_type")
    if not comp or not ptype:
        return
    try:
        job_dir = _get_job_diag_dir(comp, ptype)
        job_dir.mkdir(parents=True, exist_ok=True)
        thread_file = job_dir / f"thread_{tid}.json"
        thread_file.write_text(json.dumps(slot, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def read_persisted_thread_states(company: str, property_type: str) -> list[dict[str, Any]]:
    """Read all per-thread JSON files for a job (safe to call from parent watchdog process)."""
    job_dir = _get_job_diag_dir(company, property_type)
    states: list[dict[str, Any]] = []
    if not job_dir.exists():
        return states
    now_ts = time.time()
    for fpath in sorted(job_dir.glob(THREAD_STATE_GLOB)):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                started = float(data.get("phase_started_at") or data.get("updated_at") or now_ts)
                data["elapsed_in_phase_sec"] = round(max(0.0, now_ts - started), 2)
                states.append(data)
        except Exception:
            continue
    return states


def collect_job_thread_activities(company: str, property_type: str) -> list[dict[str, Any]]:
    """Alias for read_persisted_thread_states."""
    return read_persisted_thread_states(company, property_type)


def collect_in_process_thread_stacks() -> list[dict[str, Any]]:
    """Collect current Python stack traces for all alive threads in the current process."""
    frames = sys._current_frames()
    thread_map = {t.ident: t for t in threading.enumerate() if t.ident is not None}
    now_ts = time.time()
    results: list[dict[str, Any]] = []

    for tid, frame in frames.items():
        t_obj = thread_map.get(tid)
        t_name = t_obj.name if t_obj else f"Thread-{tid}"
        is_daemon = bool(t_obj.daemon) if t_obj else False
        slot = _thread_slots.get(tid, {})
        started = float(slot.get("phase_started_at") or slot.get("updated_at") or now_ts)
        stack_lines = traceback.format_stack(frame)
        results.append({
            "thread_id": tid,
            "thread_name": t_name,
            "daemon": is_daemon,
            "phase": slot.get("phase", ""),
            "current_url": slot.get("current_url", ""),
            "parent_list_url": slot.get("parent_list_url", ""),
            "elapsed_in_phase_sec": round(max(0.0, now_ts - started), 2) if slot else 0.0,
            "stack_trace": "".join(stack_lines[-15:]),
        })
    return results


def collect_asyncio_task_diagnostics() -> list[dict[str, Any]]:
    """Inspect active asyncio tasks if an event loop is running."""
    tasks_info: list[dict[str, Any]] = []
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            for task in asyncio.all_tasks(loop):
                if task.done():
                    continue
                coro = task.get_coro()
                coro_name = getattr(coro, "__qualname__", str(coro))
                frames = task.get_stack(limit=5)
                frame_strs = [f"{f.f_code.co_filename}:{f.f_lineno} in {f.f_code.co_name}" for f in frames]
                tasks_info.append({
                    "task_name": task.get_name(),
                    "coroutine": coro_name,
                    "frames": frame_strs,
                })
    except Exception:
        pass
    return tasks_info


def collect_database_connection_diagnostics() -> dict[str, Any]:
    """Collect Django database connection states and ProxySQL socket reachability."""
    db_diag: dict[str, Any] = {
        "connections_open": 0,
        "aliases": {},
        "proxysql_host": os.getenv("DB_HOST", "127.0.0.1"),
        "proxysql_port": int(os.getenv("DB_PORT", "6033") or 6033),
        "proxysql_reachable": False,
        "proxysql_ping_ms": None,
    }
    try:
        from django.db import connections

        open_cnt = 0
        for alias in connections:
            conn = connections[alias]
            is_open = conn.connection is not None
            if is_open:
                open_cnt += 1
            db_diag["aliases"][alias] = {
                "is_open": is_open,
                "in_atomic_block": bool(getattr(conn, "in_atomic_block", False)),
                "queries_logged": len(getattr(conn, "queries_log", [])),
            }
        db_diag["connections_open"] = open_cnt
    except Exception as e:
        db_diag["django_db_error"] = str(e)

    host = db_diag["proxysql_host"]
    port = db_diag["proxysql_port"]
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=1.5):
            db_diag["proxysql_reachable"] = True
            db_diag["proxysql_ping_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    except OSError as e:
        db_diag["proxysql_reachable"] = False
        db_diag["proxysql_error"] = str(e)

    return db_diag


def collect_network_and_hardware_diagnostics(target_pid: int | None = None) -> dict[str, Any]:
    """Collect hardware (CPU, memory, child processes) and network socket states."""
    from package.utils.newrelic_helper import collect_hardware_resource_metrics

    return collect_hardware_resource_metrics(target_pid=target_pid)


def _merge_single_thread_entry(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for k, v in incoming.items():
        if v or k not in merged:
            merged[k] = v
    return merged


def _merge_thread_diagnostics(
    persisted_threads: list[dict[str, Any]],
    in_proc_threads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined_by_tid = {
        pt["thread_id"]: dict(pt) for pt in persisted_threads if pt.get("thread_id") is not None
    }
    for it in in_proc_threads:
        tid = it.get("thread_id")
        if tid is not None:
            combined_by_tid[tid] = _merge_single_thread_entry(combined_by_tid.get(tid, {}), it)

    source_threads = list(combined_by_tid.values()) or in_proc_threads or persisted_threads
    return sorted(
        source_threads,
        key=lambda t: float(t.get("elapsed_in_phase_sec", 0.0)),
        reverse=True,
    )


def _extract_active_urls_and_phases(
    sorted_threads: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    active_urls: list[str] = []
    parent_urls: list[str] = []
    active_phases: list[str] = []
    for t in sorted_threads:
        phase = t.get("phase", "")
        u = t.get("current_url", "")
        pu = t.get("parent_list_url", "")
        if phase and phase != "idle":
            active_phases.append(
                f"{t.get('thread_name', t.get('thread_id'))}:{phase}({t.get('elapsed_in_phase_sec', 0)}s)"
            )
        if u and u not in active_urls:
            active_urls.append(u)
        if pu and pu not in parent_urls:
            parent_urls.append(pu)
    return active_urls, parent_urls, active_phases


def build_hang_diagnostic_snapshot(
    company: str,
    property_type: str,
    *,
    target_pid: int | None = None,
    in_process: bool = True,
    reason: str = "HangSilentFailure",
) -> dict[str, Any]:
    """Assemble a complete diagnostic snapshot for a hung or failing crawler job."""
    persisted_threads = read_persisted_thread_states(company, property_type)
    in_proc_threads = collect_in_process_thread_stacks() if in_process else []
    sorted_threads = _merge_thread_diagnostics(persisted_threads, in_proc_threads)
    active_urls, parent_urls, active_phases = _extract_active_urls_and_phases(sorted_threads)

    hw_net = collect_network_and_hardware_diagnostics(target_pid=target_pid)
    db_diag = collect_database_connection_diagnostics()
    asyncio_tasks = collect_asyncio_task_diagnostics() if in_process else []

    return {
        "timestamp": datetime.datetime.now(JST).isoformat(),
        "company": company,
        "property_type": property_type,
        "pid": target_pid or os.getpid(),
        "reason": reason,
        "primary_target_url": active_urls[0] if active_urls else "",
        "primary_parent_list_url": parent_urls[0] if parent_urls else "",
        "active_urls": active_urls[:20],
        "active_phases": active_phases[:20],
        "hardware_and_network": hw_net,
        "database": db_diag,
        "threads": sorted_threads[:25],
        "persisted_thread_states": persisted_threads[:25],
        "asyncio_tasks": asyncio_tasks[:25],
    }


def format_snapshot_summary_text(snapshot: dict[str, Any]) -> str:
    """Format a human-readable diagnostic summary and stack trace string for logs & FailureRecord."""
    hw = snapshot.get("hardware_and_network", {})
    db = snapshot.get("database", {})
    lines: list[str] = [
        f"=== HANG / DIAGNOSTIC SNAPSHOT [{snapshot.get('company')}/{snapshot.get('property_type')}] "
        f"PID={snapshot.get('pid')} reason={snapshot.get('reason')} ===",
        f"Primary URL: {snapshot.get('primary_target_url') or '(none)'}",
        f"Parent List URL: {snapshot.get('primary_parent_list_url') or '(none)'}",
        f"Active Phases: {', '.join(snapshot.get('active_phases', [])) or '(none)'}",
        f"Active URLs ({len(snapshot.get('active_urls', []))}): {', '.join(snapshot.get('active_urls', [])[:5])}",
        f"Resources: CPU(proc={hw.get('cpuPercent', 0)}%, sys={hw.get('systemCpuPercent', 0)}%) | "
        f"Mem(proc={hw.get('memoryUsageMb', 0)}MB, sys={hw.get('systemMemoryPercent', 0)}%) | "
        f"Threads={hw.get('activeThreadsCount', 0)} | ChildProcs={hw.get('childProcessCount', 0)}",
        f"Network: TCP(total={hw.get('tcpTotalCount', 0)}, ESTAB={hw.get('tcpEstablishedCount', 0)}, "
        f"SYN_SENT={hw.get('tcpSynSentCount', 0)}, CLOSE_WAIT={hw.get('tcpCloseWaitCount', 0)}, "
        f"TIME_WAIT={hw.get('tcpTimeWaitCount', 0)}) | "
        f"Endpoints={', '.join(hw.get('remoteEndpoints', [])[:8])}",
        f"Database: open_conns={db.get('connections_open', 0)} | "
        f"ProxySQL({db.get('proxysql_host')}:{db.get('proxysql_port')}) "
        f"reachable={db.get('proxysql_reachable')} ping_ms={db.get('proxysql_ping_ms')}",
    ]

    for t in snapshot.get("threads", [])[:10]:
        lines.append(
            f"\n--- Thread [{t.get('thread_name')}] (tid={t.get('thread_id')}, "
            f"phase={t.get('phase')}, elapsed={t.get('elapsed_in_phase_sec')}s, "
            f"url={t.get('current_url')}) ---"
        )
        st = t.get("stack_trace", "")
        if st:
            lines.append(st.rstrip())

    return "\n".join(lines)


def format_hang_diagnostic_summary(snapshot: dict[str, Any]) -> str:
    """Alias for format_snapshot_summary_text."""
    return format_snapshot_summary_text(snapshot)


def save_hang_diagnostic_snapshot(
    company: str,
    property_type: str,
    *,
    target_pid: int | None = None,
    in_process: bool = True,
    include_current_process_stacks: bool | None = None,
    reason: str = "HangSilentFailure",
    date_str: str | None = None,
) -> dict[str, Any]:
    """Capture, persist to disk, log, and send to New Relic a full hang diagnostic snapshot."""
    use_in_proc = include_current_process_stacks if include_current_process_stacks is not None else in_process
    snapshot = build_hang_diagnostic_snapshot(
        company,
        property_type,
        target_pid=target_pid,
        in_process=use_in_proc,
        reason=reason,
    )
    summary_text = format_snapshot_summary_text(snapshot)

    target_date = date_str or datetime.datetime.now(JST).strftime("%Y%m%d")
    diag_dir = _CRAWLER_ROOT / "logs" / "runs" / target_date / "diagnostics"
    try:
        diag_dir.mkdir(parents=True, exist_ok=True)
        out_path = diag_dir / f"hang_{company}_{property_type}.json"
        out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot["diagnostic_file"] = str(out_path)
    except Exception as e:
        logging.warning(f"Failed to write hang diagnostic file: {e}")

    snapshot["summary_text"] = summary_text
    logging.error(summary_text)

    try:
        from package.utils.newrelic_helper import record_hang_diagnostic_event

        record_hang_diagnostic_event(snapshot)
    except Exception:
        pass

    return snapshot
