#!/usr/bin/env python3
"""Daily TTL-Expired Direct-URL Crawl & Delisted Flagging Runner (Issue #1415).

Queries all published properties whose detail fetch timestamp (`last_detail_fetched_at`,
falling back to property `inputDateTime` / `updateDateTime`) is older than `ttl_days`
(default: 14 days), opens every URL directly via `ParseDetailPageAsyncBase`:
  - If delisted (`ListingEndedException` / HTTP 404 / 410): marks `PropertyEvaluation.is_published=False`
    and sets `delisted_at=now`.
  - If still active: parses and saves full property details, price revision history,
    integrity validation, and refreshes `last_detail_fetched_at=now`.
  - If blocked/maintenance/transient error: preserves `is_published=True` (zero false delisting).

Supports `--ensure-local-prod-infra` to satisfy AGENTS.md Principle 1.1 (Local Production Execution):
  - Host Python direct execution (`EXECUTION_ENV=host`).
  - Verifies GCE `proxysql-instance-prod` (`asia-northeast1-a`) is `RUNNING` (auto-starts if stopped).
  - Establishes headless IAP tunnel to `127.0.0.1:6033` if not already open.
  - Verifies `SELECT 1` DB connectivity before crawling (fail-fast on connection error).
  - Cleans up self-started IAP tunnel and invokes `ensure_resources_stopped.py` on exit.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import datetime
import functools
import gc
import inspect
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from types import TracebackType
from typing import IO, Any, Self

import aiohttp

# Resolve src/crawler path dynamically without hardcoding /app/
_CUR_FILE = Path(__file__).resolve()
for _parent in _CUR_FILE.parents:
    if (_parent / "setup_env.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

import setup_env  # noqa: E402, F401
from asgiref.sync import sync_to_async  # noqa: E402
from django.db import DatabaseError, InterfaceError, OperationalError, close_old_connections, connection, connections  # noqa: E402
from django.utils import timezone  # noqa: E402

from package.api.adaptive_concurrency import AdaptiveConcurrencyController  # noqa: E402
from package.api.api import ParseDetailPageAsyncBase, header as DEFAULT_HTTP_HEADERS  # noqa: E402
from package.api.differential import _is_ttl_expired  # noqa: E402
from package.models.evaluation import PropertyEvaluation, PropertyPriceHistory  # noqa: E402
from package.parser.baseParser import SkipPropertyException  # noqa: E402
from package.site_registry import SiteRegistry  # noqa: E402
from package.utils.crawler_diagnostics import record_thread_activity  # noqa: E402
from package.utils.data_validator import PropertyDataValidator, apply_integrity_transition  # noqa: E402
from package.utils.git_version import get_current_git_sha  # noqa: E402
from package.utils.property_type_detector import PropertyTypeDetector  # noqa: E402
from package.utils.report import CrawlerReporter  # noqa: E402
from package.utils.url_matcher import UrlMatcher  # noqa: E402
from package.utils.url_router import UrlRouter  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 14
DEFAULT_CONCURRENCY = 40
DEFAULT_DOMAIN_CONCURRENCY = 3
DEFAULT_PLAYWRIGHT_CONCURRENCY = 2
DEFAULT_DB_CONCURRENCY = 8
DEFAULT_DB_BATCH_SIZE = 100
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_MAX_CONSECUTIVE_FAILURES = 25
POST_START_SETTLE_SEC = 25.0
DEFAULT_PROD_GCS_BUCKET = "realestate-images-sumifu-prod"
JST = datetime.timezone(datetime.timedelta(hours=9), name="JST")
PLAYWRIGHT_HEAVY_COMPANIES: frozenset[str] = frozenset(
    {"athome", "mizuho", "sekisui", "smtrc", "kenbiya"}
)
_TRANSIENT_DB_ERROR_TOKENS = (
    "2002",
    "2003",
    "2006",
    "2013",
    "lost connection",
    "gone away",
    "can't connect",
    "connection reset",
    "closed the connection",
)


@dataclass(frozen=True)
class TtlTarget:
    property_url: str
    company: str
    property_type: str
    property_id: int = 0
    evaluation_id: int | None = None


def _normalize_url_key(url: str) -> str:
    return UrlMatcher.normalize(url).rstrip("/")


def _resolve_gcloud_binary(explicit_bin: str | None = None) -> str:
    if explicit_bin:
        return explicit_bin
    env_bin = os.getenv("GCLOUD_PATH", "").strip()
    if env_bin and Path(env_bin).exists():
        return env_bin
    if os.name == "nt":
        found_cmd = shutil.which("gcloud.cmd")
        if found_cmd:
            return found_cmd
    return shutil.which("gcloud") or ("gcloud.cmd" if os.name == "nt" else "gcloud")


def _headless_creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run_headless_cmd(cmd: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=_headless_creationflags(),
    )


def _is_tcp_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _spawn_iap_tunnel_process(
    gcloud_bin: str,
    project_id: str,
    zone: str,
    instance_name: str,
    local_host: str,
    local_port: int,
    stderr_stream: IO[str] | int = subprocess.DEVNULL,
) -> subprocess.Popen[str]:
    cmd = [
        gcloud_bin,
        "compute",
        "start-iap-tunnel",
        instance_name,
        str(local_port),
        f"--local-host-port={local_host}:{local_port}",
        f"--zone={zone}",
        f"--project={project_id}",
        "--quiet",
    ]
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_stream,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_headless_creationflags(),
    )


def verify_db_select_one() -> bool:
    """Execute SELECT 1 on the configured Django DB connection; raises immediately on failure."""
    close_old_connections()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
    return bool(row and row[0] == 1)


def compute_next_jst_deadline(
    hhmm: str,
    now_utc: datetime.datetime | None = None,
) -> datetime.datetime:
    """Parse 'HH:MM' in Asia/Tokyo (JST) and return the next upcoming UTC datetime."""
    cleaned = hhmm.strip()
    parts = cleaned.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"Invalid --stop-at-jst value '{hhmm}': expected HH:MM (e.g. 00:50)")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid --stop-at-jst value '{hhmm}': expected HH:MM between 00:00 and 23:59")
    ref_utc = now_utc or datetime.datetime.now(datetime.UTC)
    if ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=datetime.UTC)
    now_jst = ref_utc.astimezone(JST)
    candidate_jst = now_jst.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate_jst <= now_jst:
        candidate_jst += datetime.timedelta(days=1)
    return candidate_jst.astimezone(datetime.UTC)


def _run_safe_proxysql_stop_check(skip_traffic_check: bool = False) -> None:
    """Delegate idle ProxySQL stop check to ensure_resources_stopped.py (Shared Infra Protection)."""
    safety_script = _CUR_FILE.parents[1] / "ensure_resources_stopped.py"
    if not safety_script.exists():
        return
    cmd = [sys.executable, str(safety_script), "--grace-period-sec", "0"]
    if skip_traffic_check:
        cmd.append("--skip-traffic-check")
    try:
        _run_headless_cmd(cmd, timeout=90.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Safety-net ProxySQL stop check encountered an error: %s", exc)


def _is_transient_db_disconnect(exc: BaseException) -> bool:
    if not isinstance(exc, (OperationalError, InterfaceError, DatabaseError)):
        return False
    lowered = str(exc).lower()
    if any(token in lowered for token in _TRANSIENT_DB_ERROR_TOKENS):
        return True
    first_arg = exc.args[0] if getattr(exc, "args", None) else None
    return first_arg in (2002, 2003, 2006, 2013)


class LocalProdInfraContext:
    """Enforces AGENTS.md Principle 1.1 & Principle 1 for local production execution."""

    def __init__(
        self,
        gcloud_bin: str | None = None,
        project_id: str | None = None,
        zone: str | None = None,
        instance_name: str | None = None,
        local_host: str | None = None,
        local_port: int | None = None,
        stop_if_idle_on_exit: bool = True,
        force_stop_proxysql_on_exit: bool = False,
        enable_tunnel_watchdog: bool = True,
    ) -> None:
        self.gcloud_bin: str = _resolve_gcloud_binary(gcloud_bin)
        self.project_id: str = project_id or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "sumifu"
        region = os.getenv("GCP_REGION") or "asia-northeast1"
        self.zone: str = zone or os.getenv("PROXYSQL_ZONE") or f"{region}-a"
        self.instance_name: str = instance_name or os.getenv("PROXYSQL_INSTANCE_NAME") or "proxysql-instance-prod"
        self.local_host: str = local_host or os.getenv("DB_HOST") or "127.0.0.1"
        port_raw = os.getenv("DB_PORT") or "6033"
        self.local_port: int = local_port if local_port is not None else int(port_raw)
        self.stop_if_idle_on_exit = stop_if_idle_on_exit
        self.force_stop_proxysql_on_exit = force_stop_proxysql_on_exit
        self.enable_tunnel_watchdog = enable_tunnel_watchdog
        self.started_proxysql = False
        self.started_tunnel = False
        self._tunnel_proc: subprocess.Popen[str] | None = None
        self._tunnel_err_fp: IO[str] | None = None
        self._tunnel_err_path: Path | None = None
        self._tunnel_lock = threading.Lock()
        self._stop_watchdog = threading.Event()
        self._watchdog_thread: threading.Thread | None = None

    def _apply_local_prod_storage_defaults(self) -> None:
        os.environ.setdefault("STORAGE_BACKEND", "gcs")
        os.environ.setdefault("GCS_BUCKET_NAME", DEFAULT_PROD_GCS_BUCKET)

    def _get_proxysql_status(self) -> str:
        res = _run_headless_cmd(
            [
                self.gcloud_bin,
                "compute",
                "instances",
                "describe",
                self.instance_name,
                f"--zone={self.zone}",
                f"--project={self.project_id}",
                "--format=value(status)",
            ],
            timeout=30.0,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Failed to query GCE instance {self.instance_name}: {res.stderr.strip() or res.stdout.strip()}"
            )
        return res.stdout.strip().upper()

    def _ensure_proxysql_running(self) -> None:
        status = self._get_proxysql_status()
        logger.info("[LocalProdInfra] GCE %s status: %s", self.instance_name, status)
        if status == "RUNNING":
            return

        logger.info("[LocalProdInfra] Starting GCE instance %s (%s)...", self.instance_name, self.zone)
        start_res = _run_headless_cmd(
            [
                self.gcloud_bin,
                "compute",
                "instances",
                "start",
                self.instance_name,
                f"--zone={self.zone}",
                f"--project={self.project_id}",
                "--quiet",
            ],
            timeout=120.0,
        )
        if start_res.returncode != 0:
            raise RuntimeError(
                f"Failed to start {self.instance_name}: {start_res.stderr.strip() or start_res.stdout.strip()}"
            )
        self.started_proxysql = True

        for _ in range(24):
            if self._get_proxysql_status() == "RUNNING":
                # Allow metadata_startup_script's `systemctl restart proxysql` to complete on cold boot
                time.sleep(POST_START_SETTLE_SEC)
                return
            time.sleep(5)
        raise TimeoutError(f"GCE instance {self.instance_name} did not reach RUNNING within 120s.")

    def _wait_until_local_tunnel_ready(self) -> bool:
        for _ in range(45):
            if self._tunnel_proc is None or self._tunnel_proc.poll() is not None:
                return False
            if _is_tcp_port_open(self.local_host, self.local_port):
                logger.info("[LocalProdInfra] IAP tunnel listening on %s:%d", self.local_host, self.local_port)
                return True
            time.sleep(1)
        return False

    def _open_tunnel_stderr_tempfile(self) -> IO[str]:
        fd, raw_path = tempfile.mkstemp(prefix="iap_tunnel_", suffix=".err.log")
        self._tunnel_err_path = Path(raw_path)
        self._tunnel_err_fp = os.fdopen(fd, "w", encoding="utf-8", errors="replace")
        return self._tunnel_err_fp

    def _read_tunnel_stderr_tail(self) -> str:
        if self._tunnel_err_fp is not None:
            try:
                self._tunnel_err_fp.flush()
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error flushing IAP tunnel stderr tempfile.")
        if self._tunnel_err_path is None or not self._tunnel_err_path.exists():
            return ""
        try:
            return self._tunnel_err_path.read_text(encoding="utf-8", errors="replace")[-400:].strip()
        except Exception:  # noqa: BLE001
            return ""

    def _cleanup_tunnel_stderr_tempfile(self) -> None:
        if self._tunnel_err_fp is not None:
            try:
                self._tunnel_err_fp.close()
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error closing IAP tunnel stderr tempfile.")
            self._tunnel_err_fp = None
        if self._tunnel_err_path is not None:
            try:
                self._tunnel_err_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error unlinking IAP tunnel stderr tempfile.")
            self._tunnel_err_path = None

    def _spawn_and_wait_tunnel(self, max_tunnel_attempts: int) -> None:
        last_err_msg = ""
        for attempt in range(max_tunnel_attempts):
            logger.info(
                "[LocalProdInfra] Starting headless IAP tunnel to %s:%d (attempt %d/%d)...",
                self.local_host,
                self.local_port,
                attempt + 1,
                max_tunnel_attempts,
            )
            err_fp = self._open_tunnel_stderr_tempfile()
            self._tunnel_proc = _spawn_iap_tunnel_process(
                gcloud_bin=self.gcloud_bin,
                project_id=self.project_id,
                zone=self.zone,
                instance_name=self.instance_name,
                local_host=self.local_host,
                local_port=self.local_port,
                stderr_stream=err_fp,
            )
            self.started_tunnel = True
            if self._wait_until_local_tunnel_ready():
                return

            rc = self._tunnel_proc.returncode if self._tunnel_proc else None
            err_out = self._read_tunnel_stderr_tail() if rc is not None else ""
            last_err_msg = f"rc={rc}: {err_out}" if rc is not None else "timed out waiting for local port"
            self._terminate_tunnel_unlocked()
            if attempt < max_tunnel_attempts - 1:
                logger.info("[LocalProdInfra] Waiting for ProxySQL port 6033 warmup (%s)...", last_err_msg[:120])
                time.sleep(8)

        raise RuntimeError(f"IAP tunnel on {self.local_host}:{self.local_port} failed after retries ({last_err_msg}).")

    def _ensure_iap_tunnel(self) -> None:
        with self._tunnel_lock:
            if _is_tcp_port_open(self.local_host, self.local_port):
                logger.info("[LocalProdInfra] Reusing existing tunnel at %s:%d", self.local_host, self.local_port)
                return
            max_tunnel_attempts = 6 if self.started_proxysql else 3
            self._spawn_and_wait_tunnel(max_tunnel_attempts)

    def ensure_tunnel_alive(self) -> bool:
        """Respawn self-started IAP tunnel if it exited (e.g. multi-hour GCP IAP WebSocket rotation)."""
        with self._tunnel_lock:
            if not self.started_tunnel or self._stop_watchdog.is_set():
                return False
            if self._tunnel_proc is not None and self._tunnel_proc.poll() is None:
                return False
            rc = self._tunnel_proc.returncode if self._tunnel_proc is not None else None
            logger.warning(
                "[LocalProdInfra] Detected exited IAP tunnel (rc=%s); respawning headless tunnel on %s:%d...",
                rc,
                self.local_host,
                self.local_port,
            )
            self._terminate_tunnel_unlocked()
            if _is_tcp_port_open(self.local_host, self.local_port):
                return False
            self._spawn_and_wait_tunnel(max_tunnel_attempts=3)
            return True

    def _tunnel_watchdog_loop(self) -> None:
        while not self._stop_watchdog.wait(timeout=5.0):
            try:
                self.ensure_tunnel_alive()
            except Exception as exc:  # noqa: BLE001
                logger.warning("[LocalProdInfra] IAP tunnel watchdog retry failed: %s", exc)

    def _start_watchdog_if_needed(self) -> None:
        if not self.enable_tunnel_watchdog or not self.started_tunnel:
            return
        self._stop_watchdog.clear()
        self._watchdog_thread = threading.Thread(
            target=self._tunnel_watchdog_loop,
            name="iap-tunnel-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _stop_watchdog_thread(self) -> None:
        self._stop_watchdog.set()
        if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)
        self._watchdog_thread = None

    def _verify_db_with_warmup_retries(self) -> None:
        last_err: Exception | None = None
        max_attempts = 6 if (self.started_proxysql or self.started_tunnel) else 2
        for attempt in range(max_attempts):
            try:
                if verify_db_select_one():
                    logger.info("[LocalProdInfra] Verified DB connectivity (SELECT 1 == 1).")
                    return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Ignored error closing connection during warmup retry.")
                if attempt < max_attempts - 1:
                    time.sleep(4)
                else:
                    raise
        if last_err is not None:
            raise last_err
        raise RuntimeError("DB SELECT 1 returned unexpected result.")

    def _terminate_tunnel_unlocked(self) -> None:
        if self._tunnel_proc is not None:
            try:
                if self._tunnel_proc.poll() is None:
                    self._tunnel_proc.terminate()
                    self._tunnel_proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    self._tunnel_proc.kill()
                except Exception:  # noqa: BLE001
                    logger.debug("Ignored error killing IAP tunnel process.")
            finally:
                self._tunnel_proc = None
        self._cleanup_tunnel_stderr_tempfile()

    def _terminate_tunnel(self) -> None:
        with self._tunnel_lock:
            self._terminate_tunnel_unlocked()

    def __enter__(self) -> Self:
        self._apply_local_prod_storage_defaults()
        try:
            self._ensure_proxysql_running()
            self._ensure_iap_tunnel()
            self._verify_db_with_warmup_retries()
            self._start_watchdog_if_needed()
        except Exception:
            self._stop_watchdog_thread()
            self._terminate_tunnel()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop_watchdog_thread()
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            logger.debug("Ignored error closing DB connection on exit.")
        if self.started_tunnel:
            logger.info("[LocalProdInfra] Closing self-started IAP tunnel...")
            self._terminate_tunnel()
        if self.stop_if_idle_on_exit and (self.started_proxysql or self.force_stop_proxysql_on_exit):
            logger.info(
                "[LocalProdInfra] Running safe stop check for ProxySQL (skip_traffic_check=%s)...",
                self.force_stop_proxysql_on_exit,
            )
            _run_safe_proxysql_stop_check(skip_traffic_check=self.force_stop_proxysql_on_exit)


def _index_model_timestamps(
    model_rows_by_entry: list[tuple[str, str, list[dict[str, Any]]]],
) -> dict[str, dict[str, Any]]:
    url_meta: dict[str, dict[str, Any]] = {}
    for comp, ptype, rows in model_rows_by_entry:
        for row in rows:
            raw_url = str(row.get("pageUrl") or "").strip()
            if not raw_url:
                continue
            key = _normalize_url_key(raw_url)
            if not key or key in url_meta:
                continue
            url_meta[key] = {
                "pageUrl": raw_url,
                "company": comp,
                "property_type": ptype,
                "id": int(row.get("id") or 0),
                "base_dt": row.get("inputDateTime") or row.get("updateDateTime"),
            }
    return url_meta


def _should_queue_published_eval(
    ev: dict[str, Any],
    model_meta: dict[str, Any] | None,
    now: Any,
    ttl_days: int,
) -> bool:
    last_fetched = ev.get("last_detail_fetched_at")
    if last_fetched is not None:
        return _is_ttl_expired(last_fetched, now, ttl_days)
    if model_meta is None:
        return True
    fallback_dt = model_meta.get("base_dt")
    return True if fallback_dt is None else _is_ttl_expired(fallback_dt, now, ttl_days)


def interleave_targets_by_company(targets: list[TtlTarget]) -> list[TtlTarget]:
    """Round-robin interleave targets across companies so no single domain is hammered in bursts."""
    buckets: dict[str, deque[TtlTarget]] = defaultdict(deque)
    company_order: list[str] = []
    for target in targets:
        comp = target.company or "unknown"
        if comp not in buckets:
            company_order.append(comp)
        buckets[comp].append(target)

    interleaved: list[TtlTarget] = []
    active_companies = deque(company_order)
    while active_companies:
        comp = active_companies.popleft()
        q = buckets[comp]
        if q:
            interleaved.append(q.popleft())
        if q:
            active_companies.append(comp)
    return interleaved


def _extract_expired_from_evaluations(
    eval_rows: list[dict[str, Any]],
    model_meta_by_key: dict[str, dict[str, Any]],
    now: Any,
    ttl_days: int,
    company_filter: set[str] | None,
) -> tuple[list[TtlTarget], set[str], set[str]]:
    seen_eval_keys: set[str] = set()
    queued_keys: set[str] = set()
    targets: list[TtlTarget] = []

    for ev in eval_rows:
        raw_url = str(ev.get("property_url") or "").strip()
        key = _normalize_url_key(raw_url) if raw_url else ""
        if not key:
            continue
        seen_eval_keys.add(key)

        comp = str(ev.get("company") or "unknown").lower()
        if not ev.get("is_published", True) or (company_filter and comp not in company_filter):
            continue
        if key in queued_keys or not _should_queue_published_eval(ev, model_meta_by_key.get(key), now, ttl_days):
            continue

        queued_keys.add(key)
        targets.append(
            TtlTarget(
                property_url=raw_url,
                company=comp,
                property_type=str(ev.get("property_type") or "unknown"),
                property_id=int(ev.get("property_id") or 0),
                evaluation_id=ev.get("id"),
            )
        )
    return targets, seen_eval_keys, queued_keys


def _extract_expired_unevaluated_models(
    model_meta_by_key: dict[str, dict[str, Any]],
    seen_eval_keys: set[str],
    queued_keys: set[str],
    now: Any,
    ttl_days: int,
    company_filter: set[str] | None,
) -> list[TtlTarget]:
    unevaluated_targets: list[TtlTarget] = []
    for key, meta in model_meta_by_key.items():
        if key in seen_eval_keys or key in queued_keys:
            continue
        comp = str(meta["company"]).lower()
        if company_filter and comp not in company_filter:
            continue
        base_dt = meta.get("base_dt")
        if base_dt is None or _is_ttl_expired(base_dt, now, ttl_days):
            queued_keys.add(key)
            unevaluated_targets.append(
                TtlTarget(
                    property_url=meta["pageUrl"],
                    company=comp,
                    property_type=meta["property_type"],
                    property_id=meta["id"],
                    evaluation_id=None,
                )
            )
    return unevaluated_targets


def build_ttl_expired_targets_from_snapshots(
    eval_rows: list[dict[str, Any]],
    model_rows_by_entry: list[tuple[str, str, list[dict[str, Any]]]],
    now: Any,
    ttl_days: int = DEFAULT_TTL_DAYS,
    company_filter: set[str] | None = None,
) -> list[TtlTarget]:
    """Pure target selection logic across PropertyEvaluation and concrete property tables."""
    model_meta_by_key = _index_model_timestamps(model_rows_by_entry)
    targets, seen_eval_keys, queued_keys = _extract_expired_from_evaluations(
        eval_rows=eval_rows,
        model_meta_by_key=model_meta_by_key,
        now=now,
        ttl_days=ttl_days,
        company_filter=company_filter,
    )
    targets.extend(
        _extract_expired_unevaluated_models(
            model_meta_by_key=model_meta_by_key,
            seen_eval_keys=seen_eval_keys,
            queued_keys=queued_keys,
            now=now,
            ttl_days=ttl_days,
            company_filter=company_filter,
        )
    )
    return interleave_targets_by_company(targets)


def _fetch_target_snapshots_once(
    company_filter: set[str] | None,
    skip_portals: bool,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, list[dict[str, Any]]]]]:
    eval_qs = PropertyEvaluation.objects.all()
    if company_filter:
        eval_qs = eval_qs.filter(company__in=company_filter)
    eval_rows = list(
        eval_qs.values(
            "id",
            "property_url",
            "company",
            "property_type",
            "property_id",
            "is_published",
            "last_detail_fetched_at",
        ).iterator(chunk_size=5000)
    )

    entries = SiteRegistry.get_all_property_model_entries(
        skip_portals=skip_portals,
        skip_uncrawled=True,
    )
    model_rows_by_entry: list[tuple[str, str, list[dict[str, Any]]]] = []
    for model_cls, comp, ptype in entries:
        if company_filter and comp.lower() not in company_filter:
            continue
        rows = list(
            model_cls.objects.values(
                "id",
                "pageUrl",
                "inputDateTime",
                "updateDateTime",
            ).iterator(chunk_size=5000)
        )
        model_rows_by_entry.append((comp, ptype, rows))
    return eval_rows, model_rows_by_entry


def _fetch_target_snapshots_with_retry(
    company_filter: set[str] | None,
    skip_portals: bool,
    max_attempts: int = 4,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, list[dict[str, Any]]]]]:
    for attempt in range(max_attempts):
        try:
            return _fetch_target_snapshots_once(company_filter, skip_portals)
        except Exception as exc:
            if not _is_transient_db_disconnect(exc) or attempt >= max_attempts - 1:
                raise
            logger.warning(
                "[TTLRecrawl] Transient DB disconnect during target scan (attempt %d/%d: %s); reconnecting...",
                attempt + 1,
                max_attempts,
                exc,
            )
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error closing connection on target scan retry.")
            time.sleep(5.0)
    raise RuntimeError("Unreachable target snapshot retry exhaustion")


def collect_ttl_expired_targets(
    ttl_days: int = DEFAULT_TTL_DAYS,
    company: str | None = None,
    skip_portals: bool = False,
    limit: int | None = None,
) -> list[TtlTarget]:
    """Query production/configured DB for all 14-day TTL-expired published property URLs."""
    company_filter = (
        {c.strip().lower() for c in company.split(",") if c.strip()}
        if company
        else None
    )
    now = timezone.now()
    eval_rows, model_rows_by_entry = _fetch_target_snapshots_with_retry(
        company_filter=company_filter,
        skip_portals=skip_portals,
    )
    targets = build_ttl_expired_targets_from_snapshots(
        eval_rows=eval_rows,
        model_rows_by_entry=model_rows_by_entry,
        now=now,
        ttl_days=ttl_days,
        company_filter=company_filter,
    )
    if limit is not None and limit > 0:
        return targets[:limit]
    return targets


def _lookup_eval_record_with_reconnect(url: str) -> Any:
    norm = UrlMatcher.normalize(url)
    for attempt in range(2):
        try:
            return (
                PropertyEvaluation.objects.filter(property_url=url).first()
                or PropertyEvaluation.objects.filter(property_url=norm).first()
                or UrlMatcher.find_match_in_queryset(PropertyEvaluation.objects, "property_url", url)
            )
        except Exception as exc:
            if not _is_transient_db_disconnect(exc) or attempt >= 1:
                raise
            connection.close()
    return None


def _inspect_post_crawl_outcome_sync(url: str, item: Any) -> str:
    eval_rec = _lookup_eval_record_with_reconnect(url)
    if eval_rec is not None and not eval_rec.is_published:
        return "delisted"
    if item is not None:
        if eval_rec is not None and (eval_rec.needs_parser_fix or eval_rec.needs_recrawl):
            return "invalid_saved"
        return "refreshed"
    if eval_rec is not None and eval_rec.needs_parser_fix:
        return "parser_failed"
    return "transient_skipped"


def _build_shared_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.options |= ssl.OP_NO_TICKET
    try:
        ctx.set_ciphers("HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4")
    except Exception:  # noqa: BLE001
        logger.debug("Using default TLS ciphers for shared batch connector.")
    return ctx


def _strip_item_soup(item: Any) -> None:
    if item is not None and hasattr(item, "_soup"):
        try:
            delattr(item, "_soup")
        except Exception:  # noqa: BLE001
            logger.debug("Ignored error removing _soup attribute from parsed item.")


class _BoundedDbExecutor:
    """Bounded thread pool for concurrent Django ORM work without sync_to_async single-thread bottlenecks."""

    def __init__(self, max_workers: int = DEFAULT_DB_CONCURRENCY) -> None:
        self.max_workers = max(1, max_workers)
        self._sem = asyncio.Semaphore(self.max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ttl-db",
        )
        self._seen_tids: set[int] = set()
        self._tid_lock = threading.Lock()

    def _invoke_with_tid_tracking(self, fn: Callable[..., Any], *args: Any) -> Any:
        with self._tid_lock:
            self._seen_tids.add(threading.get_ident())
        return fn(*args)

    async def run(self, fn: Callable[..., Any], *args: Any) -> Any:
        async with self._sem:
            loop = asyncio.get_running_loop()
            call = functools.partial(self._invoke_with_tid_tracking, fn, *args)
            return await loop.run_in_executor(self._executor, call)

    def _close_worker_connections_sync(self) -> None:
        with self._tid_lock:
            target_count = len(self._seen_tids)
        if target_count <= 0:
            return
        barrier = threading.Barrier(min(self.max_workers, max(1, target_count)), timeout=2.0)

        def _close_on_worker() -> None:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                logger.debug("DB worker cleanup barrier timed out; closing thread connection directly.")
            try:
                connections.close_all()
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error closing worker-thread DB connections.")

        futures = [
            self._executor.submit(_close_on_worker)
            for _ in range(min(self.max_workers, max(1, target_count)))
        ]
        for fut in futures:
            try:
                fut.result(timeout=4.0)
            except Exception:  # noqa: BLE001
                logger.debug("Ignored error waiting on DB worker connection cleanup.")

    async def aclose(self) -> None:
        await asyncio.to_thread(self._close_worker_connections_sync)
        self._executor.shutdown(wait=True)


def _partition_targets_by_pool(
    targets: list[TtlTarget],
) -> tuple[deque[TtlTarget], deque[TtlTarget]]:
    static_pending: deque[TtlTarget] = deque()
    pw_pending: deque[TtlTarget] = deque()
    for target in targets:
        if (target.company or "").lower() in PLAYWRIGHT_HEAVY_COMPANIES:
            pw_pending.append(target)
        else:
            static_pending.append(target)
    return static_pending, pw_pending


_EVAL_BATCH_UPDATE_FIELDS = [
    "company",
    "property_type",
    "property_id",
    "is_published",
    "delisted_at",
    "needs_parser_fix",
    "needs_recrawl",
    "data_quality_issue",
    "heal_status",
    "failed_git_sha",
    "recrawl_attempts",
    "last_detail_fetched_at",
    "first_stage_predicted_price",
    "second_stage_predicted_price",
    "dcf_theoretical_price",
    "is_first_stage_passed",
]


@dataclass
class _FetchedOutcomeItem:
    target: TtlTarget
    kind: str  # "active" | "delisted" | "parser_failed"
    item: Any = None
    error_msg: str = ""
    proc: Any = None


def _build_url_lookup_candidates(urls: list[str]) -> list[str]:
    candidates: set[str] = set()
    for raw in urls:
        if not raw:
            continue
        candidates.add(raw)
        norm = UrlMatcher.normalize(raw)
        candidates.add(norm)
        candidates.add(norm.rstrip("/"))
        candidates.add(norm.rstrip("/") + "/")
    return list(candidates)


def _index_existing_by_norm_url(rows: list[Any], url_attr: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for row in rows:
        raw = str(getattr(row, url_attr, "") or "")
        key = _normalize_url_key(raw)
        if key and key not in indexed:
            indexed[key] = row
    return indexed


def _updatable_model_field_names(model_class: Any) -> list[str]:
    meta = getattr(model_class, "_meta", None)
    if meta is None or not hasattr(meta, "concrete_fields"):
        return []
    return [f.name for f in meta.concrete_fields if not getattr(f, "primary_key", False)]


def _prepare_single_active_model_entry(
    entry: _FetchedOutcomeItem,
    existing_map: dict[str, Any],
    current_day: datetime.date,
    current_time: datetime.datetime,
    price_revisions: list[PropertyPriceHistory],
    to_update: dict[int, Any],
    to_create: list[Any],
) -> None:
    item = entry.item
    item.pageUrl = UrlMatcher.normalize(item.pageUrl)
    key = _normalize_url_key(item.pageUrl)
    existing = existing_map.get(key)
    proc = entry.proc

    if existing is None:
        item.inputDate = current_day
        item.inputDateTime = current_time
        item.updateDateTime = current_time
        to_create.append(item)
        return

    preserve_old, broken_reasons = (
        proc._should_preserve_existing_valid_record(existing, item)
        if proc is not None
        else (False, [])
    )
    if preserve_old:
        item.id = existing.id
        logger.warning(
            "[Overwrite Protection] Preserving existing valid DB record for %s; new parse failed validation: %s",
            item.pageUrl,
            "; ".join(broken_reasons),
        )
        if proc is not None:
            proc._save_error_html_record(item, broken_reasons)
        return

    item.id = existing.id
    item.pk = existing.pk
    if hasattr(item, "_state"):
        item._state.adding = False
    item.inputDate = getattr(existing, "inputDate", None) or current_day
    item.inputDateTime = getattr(existing, "inputDateTime", None) or current_time
    item.updateDateTime = current_time

    old_p = getattr(existing, "price", None)
    new_p = getattr(item, "price", None)
    if old_p is not None and new_p is not None and old_p != new_p:
        comp = ParseDetailPageAsyncBase._detect_company_name(item) or entry.target.company
        ptype = PropertyTypeDetector.detect_from_object(item) or entry.target.property_type
        price_revisions.append(
            PropertyPriceHistory(
                property_url=item.pageUrl,
                company=comp,
                property_type=ptype,
                old_price=old_p,
                new_price=new_p,
                price_diff=new_p - old_p,
            )
        )
    to_update[int(existing.pk)] = item


def _flush_active_models_for_class(
    model_class: Any,
    entries: list[_FetchedOutcomeItem],
    batch_size: int,
    price_revisions: list[PropertyPriceHistory],
) -> None:
    urls = [str(getattr(e.item, "pageUrl", "") or e.target.property_url) for e in entries]
    candidates = _build_url_lookup_candidates(urls)
    existing_rows = list(model_class.objects.filter(pageUrl__in=candidates))
    existing_map = _index_existing_by_norm_url(existing_rows, "pageUrl")

    current_time = datetime.datetime.now()
    current_day = datetime.date.today()
    to_update: dict[int, Any] = {}
    to_create: list[Any] = []

    for entry in entries:
        _prepare_single_active_model_entry(
            entry,
            existing_map,
            current_day,
            current_time,
            price_revisions,
            to_update,
            to_create,
        )

    if to_update:
        sorted_updates = [to_update[pk] for pk in sorted(to_update)]
        fields = _updatable_model_field_names(model_class)
        if fields:
            model_class.objects.bulk_update(sorted_updates, fields=fields, batch_size=batch_size)
        else:
            for obj in sorted_updates:
                obj.save()

    if to_create:
        model_class.objects.bulk_create(to_create, batch_size=batch_size, ignore_conflicts=True)
        need_ids = [e.item for e in entries if getattr(e.item, "id", None) is None]
        if need_ids:
            refetched = list(
                model_class.objects.filter(
                    pageUrl__in=_build_url_lookup_candidates([i.pageUrl for i in need_ids])
                )
            )
            refetched_map = _index_existing_by_norm_url(refetched, "pageUrl")
            for created_item in need_ids:
                matched = refetched_map.get(_normalize_url_key(created_item.pageUrl))
                if matched is not None:
                    created_item.id = matched.id


def _apply_eval_entry_mutation(
    entry: _FetchedOutcomeItem,
    eval_rec: PropertyEvaluation | None,
    now_ts: datetime.datetime,
    cur_sha: str,
    eval_updates: dict[int, PropertyEvaluation],
    eval_creates: dict[str, PropertyEvaluation],
) -> str:
    norm_url = UrlMatcher.normalize(entry.target.property_url)
    key = _normalize_url_key(norm_url)
    comp = entry.target.company or "unknown"
    ptype = entry.target.property_type or "unknown"

    if entry.kind == "delisted":
        if eval_rec is not None:
            eval_rec.is_published = False
            eval_rec.delisted_at = now_ts
            eval_rec.needs_parser_fix = bool(eval_rec.needs_parser_fix)
            eval_rec.needs_recrawl = False
            if not eval_rec.needs_parser_fix:
                eval_rec.heal_status = "healthy"
            eval_updates[int(eval_rec.pk)] = eval_rec
        else:
            eval_creates[key] = PropertyEvaluation(
                property_url=entry.target.property_url,
                company=comp,
                property_type=ptype,
                property_id=entry.target.property_id or 0,
                is_published=False,
                delisted_at=now_ts,
                needs_recrawl=False,
                heal_status="healthy",
                analysis_status="skipped_by_budget",
            )
        return "delisted"

    if entry.kind == "parser_failed":
        issue_txt = str(entry.error_msg)[:500]
        if eval_rec is not None:
            eval_rec.needs_parser_fix = True
            eval_rec.needs_recrawl = True
            eval_rec.heal_status = "detected"
            eval_rec.failed_git_sha = cur_sha
            eval_rec.data_quality_issue = issue_txt
            eval_rec.first_stage_predicted_price = None
            eval_rec.second_stage_predicted_price = None
            eval_rec.dcf_theoretical_price = None
            eval_rec.is_first_stage_passed = False
            eval_updates[int(eval_rec.pk)] = eval_rec
        else:
            eval_creates[key] = PropertyEvaluation(
                property_url=entry.target.property_url,
                company=comp,
                property_type=ptype,
                property_id=entry.target.property_id or 0,
                is_published=True,
                needs_parser_fix=True,
                needs_recrawl=True,
                heal_status="detected",
                failed_git_sha=cur_sha,
                data_quality_issue=issue_txt,
                analysis_status="skipped_by_budget",
            )
        return "parser_failed"

    item = entry.item
    detected_comp = ParseDetailPageAsyncBase._detect_company_name(item) or comp
    detected_ptype = PropertyTypeDetector.detect_from_object(item) or ptype
    is_valid, reasons = PropertyDataValidator.validate_property(item, detected_ptype)
    prop_id = int(getattr(item, "id", 0) or entry.target.property_id or 0)

    if eval_rec is None:
        eval_rec = PropertyEvaluation(
            property_url=item.pageUrl,
            company=detected_comp,
            property_type=detected_ptype,
            property_id=prop_id,
            is_published=True,
            needs_parser_fix=not is_valid,
            needs_recrawl=not is_valid,
            data_quality_issue="; ".join(reasons),
            heal_status="healthy" if is_valid else "detected",
        )
        apply_integrity_transition(eval_rec, is_valid=is_valid, reasons=reasons, git_sha=cur_sha, now=now_ts)
        if is_valid:
            eval_rec.heal_status = "healthy"
        eval_creates[key] = eval_rec
    else:
        if prop_id and eval_rec.property_id != prop_id:
            eval_rec.property_id = prop_id
        if detected_comp != "unknown" and eval_rec.company != detected_comp:
            eval_rec.company = detected_comp
        if detected_ptype != "unknown" and eval_rec.property_type != detected_ptype:
            eval_rec.property_type = detected_ptype
        apply_integrity_transition(eval_rec, is_valid=is_valid, reasons=reasons, git_sha=cur_sha, now=now_ts)
        eval_updates[int(eval_rec.pk)] = eval_rec

    return "refreshed" if is_valid else "invalid_saved"


def _flush_fetched_batch_sync_once(
    batch: list[_FetchedOutcomeItem],
    batch_size: int,
) -> list[str]:
    active_by_model: dict[Any, list[_FetchedOutcomeItem]] = defaultdict(list)
    for entry in batch:
        if entry.kind == "active" and entry.item is not None:
            active_by_model[entry.item.__class__].append(entry)

    price_revisions: list[PropertyPriceHistory] = []
    for model_cls, group in active_by_model.items():
        _flush_active_models_for_class(model_cls, group, batch_size, price_revisions)

    if price_revisions:
        PropertyPriceHistory.objects.bulk_create(price_revisions, batch_size=batch_size)

    all_urls = [
        str(getattr(e.item, "pageUrl", "") or e.target.property_url)
        for e in batch
    ]
    eval_rows = list(
        PropertyEvaluation.objects.filter(property_url__in=_build_url_lookup_candidates(all_urls))
    )
    eval_map = _index_existing_by_norm_url(eval_rows, "property_url")

    now_ts = timezone.now()
    cur_sha = get_current_git_sha()
    eval_updates: dict[int, PropertyEvaluation] = {}
    eval_creates: dict[str, PropertyEvaluation] = {}
    outcomes: list[str] = []

    for entry in batch:
        lookup_url = str(getattr(entry.item, "pageUrl", "") or entry.target.property_url)
        existing_eval = eval_map.get(_normalize_url_key(lookup_url))
        outcomes.append(
            _apply_eval_entry_mutation(
                entry,
                existing_eval,
                now_ts,
                cur_sha,
                eval_updates,
                eval_creates,
            )
        )

    if eval_updates:
        sorted_evals = [eval_updates[pk] for pk in sorted(eval_updates)]
        PropertyEvaluation.objects.bulk_update(
            sorted_evals,
            fields=_EVAL_BATCH_UPDATE_FIELDS,
            batch_size=batch_size,
        )
    if eval_creates:
        PropertyEvaluation.objects.bulk_create(
            list(eval_creates.values()),
            batch_size=batch_size,
            ignore_conflicts=True,
        )
    return outcomes


def _flush_fetched_batch_with_retry(
    batch: list[_FetchedOutcomeItem],
    batch_size: int = DEFAULT_DB_BATCH_SIZE,
) -> list[str]:
    for attempt in range(3):
        try:
            return _flush_fetched_batch_sync_once(batch, max(1, batch_size))
        except Exception as exc:
            if not _is_transient_db_disconnect(exc) or attempt >= 2:
                raise
            logger.warning(
                "[TTLRecrawl] Transient DB disconnect during %d-item batch flush (attempt %d/3: %s); retrying...",
                len(batch),
                attempt + 1,
                exc,
            )
            connection.close()
            time.sleep(2.0)
    raise RuntimeError("Unreachable batch flush retry exhaustion")


class _TtlDbBatchBuffer:
    """Accumulates fetched detail outcomes and flushes to Cloud SQL in batches of 100."""

    def __init__(
        self,
        db_runner: _BoundedDbExecutor,
        stats_lock: asyncio.Lock,
        state: _BatchRunState,
        batch_size: int = DEFAULT_DB_BATCH_SIZE,
    ) -> None:
        self._db_runner = db_runner
        self._stats_lock = stats_lock
        self._state = state
        self._batch_size = max(1, batch_size)
        self._buf_lock = asyncio.Lock()
        self._buffer: list[_FetchedOutcomeItem] = []

    async def add(self, entry: _FetchedOutcomeItem) -> None:
        chunk_to_flush: list[_FetchedOutcomeItem] | None = None
        async with self._buf_lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._batch_size:
                chunk_to_flush = self._buffer[: self._batch_size]
                self._buffer = self._buffer[self._batch_size :]
        if chunk_to_flush is not None:
            await self._flush_chunk(chunk_to_flush)

    async def flush_remaining(self) -> None:
        while True:
            async with self._buf_lock:
                if not self._buffer:
                    return
                chunk = self._buffer[: self._batch_size]
                self._buffer = self._buffer[self._batch_size :]
            await self._flush_chunk(chunk)

    async def _flush_chunk(self, chunk: list[_FetchedOutcomeItem]) -> None:
        if not chunk:
            return
        try:
            outcomes = await self._db_runner.run(
                _flush_fetched_batch_with_retry,
                chunk,
                self._batch_size,
            )
        except Exception:
            logger.exception("[TTLRecrawl] Batch DB flush failed for %d items; falling back per-item.", len(chunk))
            outcomes = ["error"] * len(chunk)

        async with self._stats_lock:
            for outcome in outcomes:
                self._state.record_outcome(outcome)


class TtlDirectDetailProc(ParseDetailPageAsyncBase):
    """Detail-page processor supporting shared ClientSession reuse and multi-thread DB persistence."""

    def __init__(
        self,
        target: TtlTarget,
        resolved_parser: Any,
        timeout_sec: int,
        shared_session: aiohttp.ClientSession | None = None,
        db_runner: _BoundedDbExecutor | None = None,
        domain_concurrency: int = DEFAULT_DOMAIN_CONCURRENCY,
    ) -> None:
        self._resolved_parser = resolved_parser
        self._timeout_sec = timeout_sec
        self._shared_session = shared_session
        self._db_runner = db_runner
        self._domain_concurrency = max(1, domain_concurrency)
        super().__init__()
        self.company = target.company
        self.parser = resolved_parser
        self.url = target.property_url

    def _generateParser(self) -> Any:
        return self._resolved_parser

    def _getLocalPararellLimit(self) -> int:
        return self._domain_concurrency

    def _getCloudPararellLimit(self) -> int:
        return self._domain_concurrency

    def _getTimeOutSecond(self) -> int:
        return self._timeout_sec

    def _getApiKey(self) -> str:
        return ""

    async def _run_db_callable(self, fn: Callable[..., Any], *args: Any) -> Any:
        if self._db_runner is not None:
            return await self._db_runner.run(fn, *args)
        return await sync_to_async(fn, thread_sensitive=False)(*args)

    async def _execute_single_detail_fetch(self) -> Any:
        shared = self._shared_session
        if shared is None or shared.closed:
            return await super()._execute_single_detail_fetch()

        await self.semaphore.acquire()
        try:
            await self._apply_download_delay_if_needed()
            record_thread_activity("detail_page_fetch", current_url=str(self.url))
            self._touch_watchdog_progress()
            try:
                return await self.parser.parsePropertyDetailPage(session=shared, url=self.url)
            except SkipPropertyException:
                raise
            except Exception:
                logger.exception("exception get item for URL: %s", self.url)
                raise
        finally:
            self.semaphore.release()

    def _sync_persist_delisted(self) -> None:
        for attempt in range(2):
            try:
                super()._sync_persist_delisted()
                return
            except Exception as exc:
                if not _is_transient_db_disconnect(exc) or attempt >= 1:
                    raise
                connection.close()

    def _sync_persist_parser_failure_with_retry(self, err_msg: str) -> None:
        for attempt in range(2):
            try:
                self._sync_persist_parser_failure(err_msg)
                return
            except Exception as exc:
                if not _is_transient_db_disconnect(exc) or attempt >= 1:
                    raise
                connection.close()

    def _record_price_revision_sync(self, item: Any, old_p: Any, new_p: Any) -> None:
        company = self._detect_company_name(item)
        property_type = PropertyTypeDetector.detect_from_object(item)
        try:
            PropertyPriceHistory.objects.create(
                property_url=item.pageUrl,
                company=company,
                property_type=property_type,
                old_price=old_p,
                new_price=new_p,
                price_diff=new_p - old_p,
            )
            logger.info("[Price Revision] %s: %s -> %s (diff: %+d)", item.pageUrl, old_p, new_p, new_p - old_p)
        except Exception as he:  # noqa: BLE001
            logger.warning("Failed to record price history for %s: %s", item.pageUrl, he)

    def _apply_existing_or_new_timestamps(
        self,
        existing_record: Any,
        item: Any,
        current_day: datetime.date,
        current_time: datetime.datetime,
    ) -> bool:
        if not existing_record:
            item.inputDateTime = current_time
            item.inputDate = current_day
            item.updateDateTime = current_time
            return True

        preserve_old, broken_reasons = self._should_preserve_existing_valid_record(existing_record, item)
        if preserve_old:
            item.id = existing_record.id
            logger.warning(
                "[Overwrite Protection] Preserving existing valid DB record for %s; new parse failed validation: %s",
                item.pageUrl,
                "; ".join(broken_reasons),
            )
            self._save_error_html_record(item, broken_reasons)
            self._tag_integrity_sync(item)
            return False

        item.id = existing_record.id
        item._state.adding = False
        item.inputDate = existing_record.inputDate or current_day
        item.inputDateTime = existing_record.inputDateTime or current_time
        item.updateDateTime = current_time

        old_p = existing_record.price
        new_p = item.price
        if old_p is not None and new_p is not None and old_p != new_p:
            self._record_price_revision_sync(item, old_p, new_p)
        return True

    def _sync_save_property_and_integrity_once(self, item: Any) -> None:
        current_time = datetime.datetime.now()
        current_day = datetime.date.today()
        item.pageUrl = UrlMatcher.normalize(item.pageUrl)
        model_class = item.__class__
        try:
            existing_record = UrlMatcher.find_match_in_queryset(model_class.objects, "pageUrl", item.pageUrl)
        except OperationalError as e:
            if AdaptiveConcurrencyController.is_db_overload_error(e):
                AdaptiveConcurrencyController.record_db_overload(f"CheckExisting: {e}")
            if _is_transient_db_disconnect(e):
                raise
            logger.exception("Operational error checking existing record for %s, aborting save", item.pageUrl)
            return
        except Exception as exc:
            if _is_transient_db_disconnect(exc):
                raise
            logger.exception("Failed to check existing record for %s, aborting save", item.pageUrl)
            return

        if not self._apply_existing_or_new_timestamps(existing_record, item, current_day, current_time):
            return
        self._save_item_record_with_duplicate_fallback(item, model_class, current_day, current_time)
        self._tag_integrity_sync(item)

    def _sync_save_property_and_integrity_with_retry(self, item: Any) -> None:
        for attempt in range(2):
            try:
                self._sync_save_property_and_integrity_once(item)
                return
            except Exception as exc:
                if not _is_transient_db_disconnect(exc) or attempt >= 1:
                    raise
                connection.close()

    async def _save_property_and_price_history(self, item: Any) -> None:
        if self._db_runner is not None:
            await self._db_runner.run(self._sync_save_property_and_integrity_with_retry, item)
            return
        for attempt in range(2):
            try:
                await super()._save_property_and_price_history(item)
                return
            except Exception as exc:
                if not _is_transient_db_disconnect(exc) or attempt >= 1:
                    raise
                await sync_to_async(connection.close, thread_sensitive=False)()

    async def _handle_skipped_property(self) -> None:
        self._touch_watchdog_progress()
        logger.info("Skipped property processing (Listing Ended) for URL: %s", self.url)
        try:
            await self._run_db_callable(self._sync_persist_delisted)
        except OperationalError as le_err:
            if AdaptiveConcurrencyController.is_db_overload_error(le_err):
                AdaptiveConcurrencyController.record_db_overload(f"TreatPageDelisted: {le_err}")
            logger.warning("Failed to mark PropertyEvaluation as delisted for %s: %s", self.url, le_err)
        except (DatabaseError, AttributeError, ValueError) as le_err:
            logger.warning("Failed to mark PropertyEvaluation as delisted for %s: %s", self.url, le_err)

    async def _handle_parser_failure(self, error: Any) -> None:
        self._touch_watchdog_progress()
        logger.warning("Handling parser failure for URL %s: %s", self.url, error)
        try:
            await self._run_db_callable(self._sync_persist_parser_failure_with_retry, str(error))
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to persist parser failure for %s: %s", self.url, e)

    async def run_with_optional_shared_session(self) -> Any:
        shared = self._shared_session
        if shared is None or shared.closed:
            return await self._run(self.url)

        item = None
        try:
            item = await self._treatPage(shared, self._getTreatPageArg())
        except Exception:  # noqa: BLE001
            logger.exception("Error during _treatPage for %s", self.url)
            item = None
        finally:
            _strip_item_soup(item)
        return item

    async def fetch_detail_only_for_batch(self) -> tuple[Any, bool, Any]:
        """Fetch and parse detail page without per-item DB round-trips (persisted in 100-item batches)."""
        fetch_res = await self._fetch_detail_item()
        item = fetch_res[0] if len(fetch_res) > 0 else None
        is_delisted = bool(fetch_res[1]) if len(fetch_res) > 1 else False
        parser_err = fetch_res[2] if len(fetch_res) > 2 else None
        _strip_item_soup(item)
        return item, is_delisted, parser_err


def _is_crawl_single_overridden() -> bool:
    return bool(hasattr(crawl_single_ttl_target, "side_effect") or hasattr(crawl_single_ttl_target, "assert_called"))


async def _fetch_and_enqueue_batch_target(
    target: TtlTarget,
    timeout_sec: int,
    shared_session: aiohttp.ClientSession,
    db_runner: _BoundedDbExecutor,
    domain_concurrency: int,
    db_batch_buffer: _TtlDbBatchBuffer,
) -> str | None:
    parser = UrlRouter.create_parser(
        target.property_url,
        property_type=target.property_type if target.property_type != "unknown" else None,
    )
    if parser is None:
        logger.warning("[TTLRecrawl] No parser resolved for URL: %s", target.property_url)
        return "unresolved_url"

    proc = TtlDirectDetailProc(
        target=target,
        resolved_parser=parser,
        timeout_sec=timeout_sec,
        shared_session=shared_session,
        db_runner=db_runner,
        domain_concurrency=domain_concurrency,
    )
    item, is_delisted, parser_err = await proc.fetch_detail_only_for_batch()
    if item is not None:
        if os.getenv("ENABLE_INLINE_ML_EVALUATION", "false").lower() in ("true", "1"):
            await proc._handle_saved_property(item)
            return str(await db_runner.run(_inspect_post_crawl_outcome_sync, target.property_url, item))
        CrawlerReporter.success(proc.url, item.__class__.__name__)
        await db_batch_buffer.add(_FetchedOutcomeItem(target=target, kind="active", item=item, proc=proc))
        return None
    if is_delisted:
        proc._touch_watchdog_progress()
        logger.info("Buffered delisted property for 100-item DB batch: %s", proc.url)
        await db_batch_buffer.add(_FetchedOutcomeItem(target=target, kind="delisted", proc=proc))
        return None
    if parser_err is not None:
        proc._touch_watchdog_progress()
        logger.warning("Buffered parser failure for 100-item DB batch (%s): %s", proc.url, parser_err)
        await db_batch_buffer.add(
            _FetchedOutcomeItem(target=target, kind="parser_failed", error_msg=str(parser_err), proc=proc)
        )
        return None
    return "transient_skipped"


async def crawl_single_ttl_target(
    target: TtlTarget,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    session: aiohttp.ClientSession | None = None,
    db_runner: _BoundedDbExecutor | None = None,
    domain_concurrency: int = DEFAULT_DOMAIN_CONCURRENCY,
) -> str:
    """Open a single TTL-expired URL directly via ParseDetailPageAsyncBase."""
    parser = UrlRouter.create_parser(
        target.property_url,
        property_type=target.property_type if target.property_type != "unknown" else None,
    )
    if parser is None:
        logger.warning("[TTLRecrawl] No parser resolved for URL: %s", target.property_url)
        return "unresolved_url"

    proc = TtlDirectDetailProc(
        target=target,
        resolved_parser=parser,
        timeout_sec=timeout_sec,
        shared_session=session,
        db_runner=db_runner,
        domain_concurrency=domain_concurrency,
    )
    item = await proc.run_with_optional_shared_session()
    if db_runner is not None:
        return str(await db_runner.run(_inspect_post_crawl_outcome_sync, target.property_url, item))
    return await sync_to_async(_inspect_post_crawl_outcome_sync, thread_sensitive=False)(
        target.property_url, item
    )


def _accepted_optional_kwargs(
    fn: Any,
    candidate_kwargs: dict[str, Any],
) -> dict[str, Any]:
    side_effect = getattr(fn, "side_effect", None)
    target_fn = side_effect if callable(side_effect) else fn
    if not callable(target_fn):
        return {}
    try:
        sig = inspect.signature(target_fn)
    except (TypeError, ValueError):
        return {}
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return candidate_kwargs
    return {k: v for k, v in candidate_kwargs.items() if k in sig.parameters}


async def _invoke_single_ttl_target(
    target: TtlTarget,
    timeout_sec: int,
    session: aiohttp.ClientSession | None,
    db_runner: _BoundedDbExecutor | None,
    domain_concurrency: int,
) -> str:
    extra = _accepted_optional_kwargs(
        crawl_single_ttl_target,
        {
            "session": session,
            "db_runner": db_runner,
            "domain_concurrency": domain_concurrency,
        },
    )
    return await crawl_single_ttl_target(target, timeout_sec=timeout_sec, **extra)


@dataclass
class _BatchRunState:
    total: int
    max_consecutive_failures: int
    started_mono: float
    stats: dict[str, int]
    deadline_utc: datetime.datetime | None = None
    consecutive_hard_errors: int = 0
    circuit_tripped: bool = False
    deadline_reached: bool = False
    completed: int = 0

    def record_skipped(self) -> None:
        self.stats["skipped_by_circuit_breaker"] = self.stats.get("skipped_by_circuit_breaker", 0) + 1

    def record_deadline_skipped(self, count: int = 1) -> None:
        if count <= 0:
            return
        self.stats["deadline_skipped"] = self.stats.get("deadline_skipped", 0) + count

    def is_deadline_reached(self) -> bool:
        if self.deadline_reached:
            return True
        if self.deadline_utc is not None and datetime.datetime.now(datetime.UTC) >= self.deadline_utc:
            self.deadline_reached = True
            logger.info(
                "[TTLRecrawl] Reached scheduled stop deadline (%s JST). Stopping new URL fetches and flushing remaining batch...",
                self.deadline_utc.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S"),
            )
            return True
        return False

    def record_outcome(self, outcome: str) -> None:
        self.stats[outcome] = self.stats.get(outcome, 0) + 1
        self.completed += 1
        if outcome in ("refreshed", "delisted", "invalid_saved"):
            self.consecutive_hard_errors = 0
        elif outcome == "error":
            self.consecutive_hard_errors += 1
            if self.consecutive_hard_errors >= self.max_consecutive_failures:
                self.circuit_tripped = True
                logger.error(
                    "[TTLRecrawl] Circuit breaker tripped after %d consecutive hard errors.",
                    self.consecutive_hard_errors,
                )
        if self.completed % 250 == 0:
            gc.collect()
        if self.completed % 50 == 0 or self.completed == self.total:
            elapsed = max(0.001, time.monotonic() - self.started_mono)
            rate = self.completed / elapsed
            eta_min = max(0.0, (self.total - self.completed) / rate / 60.0) if rate > 0 else 0.0
            logger.info(
                "[TTLRecrawl] Progress %d/%d (%.2f URL/s, ETA %.1fm) | stats=%s",
                self.completed,
                self.total,
                rate,
                eta_min,
                self.stats,
            )


async def _execute_one_worker_target(
    target: TtlTarget,
    timeout_sec: int,
    shared_session: aiohttp.ClientSession,
    db_runner: _BoundedDbExecutor,
    domain_concurrency: int,
    db_batch_buffer: _TtlDbBatchBuffer | None,
) -> str | None:
    if db_batch_buffer is not None and not _is_crawl_single_overridden():
        return await _fetch_and_enqueue_batch_target(
            target,
            timeout_sec,
            shared_session,
            db_runner,
            domain_concurrency,
            db_batch_buffer,
        )
    return await _invoke_single_ttl_target(
        target,
        timeout_sec,
        shared_session,
        db_runner,
        domain_concurrency,
    )


async def _drain_deadline_skipped(
    pending: deque[TtlTarget],
    stats_lock: asyncio.Lock,
    state: _BatchRunState,
) -> None:
    drained = 0
    while True:
        try:
            pending.popleft()
            drained += 1
        except IndexError:
            break
    if drained > 0:
        async with stats_lock:
            state.record_deadline_skipped(drained)


async def _should_skip_before_fetch(
    stats_lock: asyncio.Lock,
    state: _BatchRunState,
    pending: deque[TtlTarget],
) -> bool:
    if state.circuit_tripped:
        async with stats_lock:
            state.record_skipped()
        return True
    async with stats_lock:
        reached = state.is_deadline_reached()
        if reached:
            state.record_deadline_skipped(1)
    if reached:
        await _drain_deadline_skipped(pending, stats_lock, state)
        return True
    return False


async def _consume_target_deque(
    pending: deque[TtlTarget],
    domain_sems: dict[str, asyncio.Semaphore],
    stats_lock: asyncio.Lock,
    state: _BatchRunState,
    timeout_sec: int,
    shared_session: aiohttp.ClientSession,
    db_runner: _BoundedDbExecutor,
    domain_concurrency: int,
    db_batch_buffer: _TtlDbBatchBuffer | None = None,
) -> None:
    while True:
        try:
            target = pending.popleft()
        except IndexError:
            return
        if await _should_skip_before_fetch(stats_lock, state, pending):
            continue

        comp_sem = domain_sems[target.company or "unknown"]
        async with comp_sem:
            if await _should_skip_before_fetch(stats_lock, state, pending):
                continue
            try:
                outcome = await _execute_one_worker_target(
                    target,
                    timeout_sec,
                    shared_session,
                    db_runner,
                    domain_concurrency,
                    db_batch_buffer,
                )
            except Exception:
                logger.exception("[TTLRecrawl] Unexpected error crawling %s", target.property_url)
                outcome = "error"

            if outcome is not None:
                async with stats_lock:
                    state.record_outcome(outcome)


async def crawl_ttl_expired_targets_async(
    targets: list[TtlTarget],
    concurrency: int = DEFAULT_CONCURRENCY,
    domain_concurrency: int = DEFAULT_DOMAIN_CONCURRENCY,
    playwright_concurrency: int = DEFAULT_PLAYWRIGHT_CONCURRENCY,
    db_concurrency: int = DEFAULT_DB_CONCURRENCY,
    db_batch_size: int = DEFAULT_DB_BATCH_SIZE,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
    deadline_utc: datetime.datetime | None = None,
) -> dict[str, int]:
    """Crawl all TTL-expired targets via isolated static/Playwright worker pools and 100-item DB batch flushes."""
    if not targets:
        return {}

    static_pending, pw_pending = _partition_targets_by_pool(targets)
    static_workers = min(len(static_pending), max(1, concurrency)) if static_pending else 0
    pw_workers = min(len(pw_pending), max(1, playwright_concurrency)) if pw_pending else 0

    static_dom_limit = max(1, domain_concurrency)
    pw_dom_limit = max(1, min(static_dom_limit, max(1, playwright_concurrency)))
    static_domain_sems: dict[str, asyncio.Semaphore] = defaultdict(
        lambda: asyncio.Semaphore(static_dom_limit)
    )
    pw_domain_sems: dict[str, asyncio.Semaphore] = defaultdict(
        lambda: asyncio.Semaphore(pw_dom_limit)
    )

    stats_lock = asyncio.Lock()
    state = _BatchRunState(
        total=len(targets),
        max_consecutive_failures=max_consecutive_failures,
        started_mono=time.monotonic(),
        stats={},
        deadline_utc=deadline_utc,
    )
    db_runner = _BoundedDbExecutor(max_workers=max(1, db_concurrency))
    batch_buffer = (
        _TtlDbBatchBuffer(
            db_runner=db_runner,
            stats_lock=stats_lock,
            state=state,
            batch_size=max(1, db_batch_size),
        )
        if db_batch_size > 1
        else None
    )
    connector = aiohttp.TCPConnector(
        limit=max(48, (static_workers + pw_workers) * 3),
        limit_per_host=max(6, static_dom_limit * 2),
        ssl=_build_shared_ssl_context(),
    )
    client_timeout = aiohttp.ClientTimeout(total=timeout_sec)

    logger.info(
        "[TTLRecrawl] Starting split pools: static_targets=%d (workers=%d, dom=%d), "
        "playwright_targets=%d (workers=%d, dom=%d), db_threads=%d, db_batch_size=%d.",
        len(static_pending),
        static_workers,
        static_dom_limit,
        len(pw_pending),
        pw_workers,
        pw_dom_limit,
        db_runner.max_workers,
        max(1, db_batch_size),
    )

    try:
        async with aiohttp.ClientSession(
            headers=DEFAULT_HTTP_HEADERS,
            connector=connector,
            timeout=client_timeout,
        ) as shared_session:
            workers = [
                asyncio.create_task(
                    _consume_target_deque(
                        static_pending,
                        static_domain_sems,
                        stats_lock,
                        state,
                        timeout_sec,
                        shared_session,
                        db_runner,
                        static_dom_limit,
                        batch_buffer,
                    )
                )
                for _ in range(static_workers)
            ]
            workers.extend(
                asyncio.create_task(
                    _consume_target_deque(
                        pw_pending,
                        pw_domain_sems,
                        stats_lock,
                        state,
                        timeout_sec,
                        shared_session,
                        db_runner,
                        pw_dom_limit,
                        batch_buffer,
                    )
                )
                for _ in range(pw_workers)
            )
            if workers:
                await asyncio.gather(*workers)
            if batch_buffer is not None:
                await batch_buffer.flush_remaining()
    finally:
        await db_runner.aclose()
        await sync_to_async(close_old_connections, thread_sensitive=False)()

    return state.stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl all TTL-expired published property URLs directly to flag delisted items & refresh active properties."
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=int(os.getenv("DIFFERENTIAL_TTL_DAYS", str(DEFAULT_TTL_DAYS))),
        help=f"Detail freshness TTL in days (default: {DEFAULT_TTL_DAYS}).",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="Optional comma-separated company filter (e.g. mitsui,sumifu).",
    )
    parser.add_argument(
        "--skip-portals",
        action="store_true",
        default=False,
        help="Skip portal models (athome, homes, kenbiya) when scanning unevaluated records.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of expired URLs to crawl (for smoke testing).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Static HTTP concurrent URL workers (default: {DEFAULT_CONCURRENCY}).",
    )
    parser.add_argument(
        "--domain-concurrency",
        type=int,
        default=DEFAULT_DOMAIN_CONCURRENCY,
        help=f"Per-company concurrent URL workers (default: {DEFAULT_DOMAIN_CONCURRENCY}).",
    )
    parser.add_argument(
        "--playwright-concurrency",
        type=int,
        default=DEFAULT_PLAYWRIGHT_CONCURRENCY,
        help=f"Dedicated concurrent workers for Playwright-heavy sites (default: {DEFAULT_PLAYWRIGHT_CONCURRENCY}).",
    )
    parser.add_argument(
        "--db-concurrency",
        type=int,
        default=DEFAULT_DB_CONCURRENCY,
        help=f"Parallel Django ORM persistence threads over ProxySQL (default: {DEFAULT_DB_CONCURRENCY}).",
    )
    parser.add_argument(
        "--db-batch-size",
        type=int,
        default=DEFAULT_DB_BATCH_SIZE,
        help=f"Number of crawled items buffered per bulk DB flush (default: {DEFAULT_DB_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"Per-URL HTTP/Playwright timeout seconds (default: {DEFAULT_TIMEOUT_SEC}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only query and print TTL-expired target counts without fetching URLs.",
    )
    parser.add_argument(
        "--ensure-local-prod-infra",
        action="store_true",
        help="Ensure GCE ProxySQL is RUNNING, establish headless IAP tunnel (127.0.0.1:6033), and verify SELECT 1 before crawling.",
    )
    parser.add_argument(
        "--stop-at-jst",
        type=str,
        default=None,
        help="Gracefully stop popping new URLs and flush pending DB batch at the next HH:MM in Asia/Tokyo (e.g. 00:50).",
    )
    parser.add_argument(
        "--stop-proxysql-on-exit",
        action="store_true",
        help="Invoke ensure_resources_stopped.py --skip-traffic-check on exit even if ProxySQL was already RUNNING before start.",
    )
    parser.add_argument(
        "--no-stop-proxysql-on-exit",
        action="store_true",
        help="Do not invoke ensure_resources_stopped.py on exit even if ProxySQL was started by this script.",
    )
    return parser


def _run_job_body(args: argparse.Namespace) -> dict[str, Any]:
    # Fail-fast DB connectivity check per AGENTS.md Principle 1.1 even without --ensure-local-prod-infra
    verify_db_select_one()
    started_at = datetime.datetime.now(datetime.UTC)
    deadline_utc: datetime.datetime | None = None
    if getattr(args, "stop_at_jst", None):
        deadline_utc = compute_next_jst_deadline(args.stop_at_jst, now_utc=started_at)
        logger.info(
            "[TTLRecrawl] Scheduled graceful stop deadline set to %s JST (%s UTC).",
            deadline_utc.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S"),
            deadline_utc.strftime("%Y-%m-%d %H:%M:%S"),
        )
    targets = collect_ttl_expired_targets(
        ttl_days=args.ttl_days,
        company=args.company,
        skip_portals=args.skip_portals,
        limit=args.limit,
    )
    by_company: dict[str, int] = defaultdict(int)
    for t in targets:
        by_company[t.company] += 1

    logger.info(
        "[TTLRecrawl] Found %d TTL-expired (>%dd) published properties across %d companies (dry_run=%s).",
        len(targets),
        args.ttl_days,
        len(by_company),
        args.dry_run,
    )
    if args.dry_run or not targets:
        return {
            "ttl_days": args.ttl_days,
            "target_count": len(targets),
            "by_company": dict(sorted(by_company.items(), key=lambda kv: -kv[1])),
            "dry_run": bool(args.dry_run),
            "stats": {},
        }

    # Prevent CRAWLER_LIMIT env var from calling os._exit(0) mid-batch unless explicitly desired
    os.environ.pop("CRAWLER_LIMIT", None)
    crawl_kwargs: dict[str, Any] = {
        "targets": targets,
        "concurrency": args.concurrency,
        "domain_concurrency": args.domain_concurrency,
        "playwright_concurrency": args.playwright_concurrency,
        "db_concurrency": args.db_concurrency,
        "db_batch_size": args.db_batch_size,
        "timeout_sec": args.timeout_sec,
    }
    if deadline_utc is not None and "deadline_utc" in _accepted_optional_kwargs(
        crawl_ttl_expired_targets_async, {"deadline_utc": deadline_utc}
    ):
        crawl_kwargs["deadline_utc"] = deadline_utc
    stats = asyncio.run(crawl_ttl_expired_targets_async(**crawl_kwargs))
    elapsed_sec = round((datetime.datetime.now(datetime.UTC) - started_at).total_seconds(), 1)
    return {
        "ttl_days": args.ttl_days,
        "target_count": len(targets),
        "by_company": dict(sorted(by_company.items(), key=lambda kv: -kv[1])),
        "dry_run": False,
        "elapsed_sec": elapsed_sec,
        "stats": stats,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = build_arg_parser().parse_args(argv)

    if args.ensure_local_prod_infra:
        with LocalProdInfraContext(
            stop_if_idle_on_exit=not args.no_stop_proxysql_on_exit,
            force_stop_proxysql_on_exit=bool(args.stop_proxysql_on_exit and not args.no_stop_proxysql_on_exit),
        ):
            summary = _run_job_body(args)
    else:
        summary = _run_job_body(args)

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
