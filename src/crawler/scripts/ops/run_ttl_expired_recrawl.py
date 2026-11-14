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
from dataclasses import dataclass
import datetime
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
from django.db import DatabaseError, InterfaceError, OperationalError, close_old_connections, connection  # noqa: E402
from django.utils import timezone  # noqa: E402

from package.api.api import ParseDetailPageAsyncBase, header as DEFAULT_HTTP_HEADERS  # noqa: E402
from package.api.differential import _is_ttl_expired  # noqa: E402
from package.models.evaluation import PropertyEvaluation  # noqa: E402
from package.parser.baseParser import SkipPropertyException  # noqa: E402
from package.site_registry import SiteRegistry  # noqa: E402
from package.utils.crawler_diagnostics import record_thread_activity  # noqa: E402
from package.utils.url_matcher import UrlMatcher  # noqa: E402
from package.utils.url_router import UrlRouter  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 14
DEFAULT_CONCURRENCY = 6
DEFAULT_DOMAIN_CONCURRENCY = 2
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_MAX_CONSECUTIVE_FAILURES = 25
POST_START_SETTLE_SEC = 25.0
DEFAULT_PROD_GCS_BUCKET = "realestate-images-sumifu-prod"
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


def _run_safe_proxysql_stop_check() -> None:
    """Delegate idle ProxySQL stop check to ensure_resources_stopped.py (Shared Infra Protection)."""
    safety_script = _CUR_FILE.parents[1] / "ensure_resources_stopped.py"
    if not safety_script.exists():
        return
    try:
        _run_headless_cmd(
            [sys.executable, str(safety_script), "--grace-period-sec", "0"],
            timeout=90.0,
        )
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
        if self.stop_if_idle_on_exit and self.started_proxysql:
            logger.info("[LocalProdInfra] Running safe idle stop check for ProxySQL...")
            _run_safe_proxysql_stop_check()


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


class TtlDirectDetailProc(ParseDetailPageAsyncBase):
    """Detail-page processor supporting optional shared aiohttp.ClientSession reuse."""

    def __init__(
        self,
        target: TtlTarget,
        resolved_parser: Any,
        timeout_sec: int,
        shared_session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._resolved_parser = resolved_parser
        self._timeout_sec = timeout_sec
        self._shared_session = shared_session
        super().__init__()
        self.company = target.company
        self.parser = resolved_parser
        self.url = target.property_url

    def _generateParser(self) -> Any:
        return self._resolved_parser

    def _getLocalPararellLimit(self) -> int:
        return DEFAULT_DOMAIN_CONCURRENCY

    def _getCloudPararellLimit(self) -> int:
        return DEFAULT_DOMAIN_CONCURRENCY

    def _getTimeOutSecond(self) -> int:
        return self._timeout_sec

    def _getApiKey(self) -> str:
        return ""

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

    async def _save_property_and_price_history(self, item: Any) -> None:
        for attempt in range(2):
            try:
                await super()._save_property_and_price_history(item)
                return
            except Exception as exc:
                if not _is_transient_db_disconnect(exc) or attempt >= 1:
                    raise
                await sync_to_async(connection.close)()

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


async def crawl_single_ttl_target(
    target: TtlTarget,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    session: aiohttp.ClientSession | None = None,
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
    )
    item = await proc.run_with_optional_shared_session()
    return await sync_to_async(_inspect_post_crawl_outcome_sync)(target.property_url, item)


def _supports_session_kwarg(fn: Any) -> bool:
    side_effect = getattr(fn, "side_effect", None)
    target_fn = side_effect if callable(side_effect) else fn
    if not callable(target_fn):
        return False
    try:
        sig = inspect.signature(target_fn)
    except (TypeError, ValueError):
        return False
    return "session" in sig.parameters or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )


async def _invoke_single_ttl_target(
    target: TtlTarget,
    timeout_sec: int,
    session: aiohttp.ClientSession | None,
) -> str:
    if _supports_session_kwarg(crawl_single_ttl_target):
        return await crawl_single_ttl_target(target, timeout_sec=timeout_sec, session=session)
    return await crawl_single_ttl_target(target, timeout_sec=timeout_sec)


@dataclass
class _BatchRunState:
    total: int
    max_consecutive_failures: int
    started_mono: float
    stats: dict[str, int]
    consecutive_hard_errors: int = 0
    circuit_tripped: bool = False
    completed: int = 0

    def record_skipped(self) -> None:
        self.stats["skipped_by_circuit_breaker"] = self.stats.get("skipped_by_circuit_breaker", 0) + 1

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


async def crawl_ttl_expired_targets_async(
    targets: list[TtlTarget],
    concurrency: int = DEFAULT_CONCURRENCY,
    domain_concurrency: int = DEFAULT_DOMAIN_CONCURRENCY,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
) -> dict[str, int]:
    """Crawl all TTL-expired targets via a bounded async worker pool and shared HTTP session."""
    if not targets:
        return {}

    worker_count = min(len(targets), max(1, concurrency))
    pending: deque[TtlTarget] = deque(targets)
    domain_sems: dict[str, asyncio.Semaphore] = defaultdict(
        lambda: asyncio.Semaphore(max(1, domain_concurrency))
    )
    stats_lock = asyncio.Lock()
    state = _BatchRunState(
        total=len(targets),
        max_consecutive_failures=max_consecutive_failures,
        started_mono=time.monotonic(),
        stats={},
    )
    connector = aiohttp.TCPConnector(
        limit=max(24, worker_count * 4),
        limit_per_host=max(4, domain_concurrency * 2),
        ssl=_build_shared_ssl_context(),
    )
    client_timeout = aiohttp.ClientTimeout(total=timeout_sec)

    async with aiohttp.ClientSession(
        headers=DEFAULT_HTTP_HEADERS,
        connector=connector,
        timeout=client_timeout,
    ) as shared_session:

        async def _pool_worker() -> None:
            while True:
                try:
                    target = pending.popleft()
                except IndexError:
                    return
                if state.circuit_tripped:
                    async with stats_lock:
                        state.record_skipped()
                    continue

                comp_sem = domain_sems[target.company or "unknown"]
                async with comp_sem:
                    if state.circuit_tripped:
                        async with stats_lock:
                            state.record_skipped()
                        continue
                    try:
                        outcome = await _invoke_single_ttl_target(target, timeout_sec, shared_session)
                    except Exception:
                        logger.exception("[TTLRecrawl] Unexpected error crawling %s", target.property_url)
                        outcome = "error"

                    async with stats_lock:
                        state.record_outcome(outcome)

        workers = [asyncio.create_task(_pool_worker()) for _ in range(worker_count)]
        await asyncio.gather(*workers)

    await sync_to_async(close_old_connections)()
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
        help=f"Global concurrent URL workers (default: {DEFAULT_CONCURRENCY}).",
    )
    parser.add_argument(
        "--domain-concurrency",
        type=int,
        default=DEFAULT_DOMAIN_CONCURRENCY,
        help=f"Per-company concurrent URL workers (default: {DEFAULT_DOMAIN_CONCURRENCY}).",
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
        "--no-stop-proxysql-on-exit",
        action="store_true",
        help="Do not invoke ensure_resources_stopped.py on exit even if ProxySQL was started by this script.",
    )
    return parser


def _run_job_body(args: argparse.Namespace) -> dict[str, Any]:
    # Fail-fast DB connectivity check per AGENTS.md Principle 1.1 even without --ensure-local-prod-infra
    verify_db_select_one()
    started_at = datetime.datetime.now(datetime.UTC)
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
    stats = asyncio.run(
        crawl_ttl_expired_targets_async(
            targets=targets,
            concurrency=args.concurrency,
            domain_concurrency=args.domain_concurrency,
            timeout_sec=args.timeout_sec,
        )
    )
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
        with LocalProdInfraContext(stop_if_idle_on_exit=not args.no_stop_proxysql_on_exit):
            summary = _run_job_body(args)
    else:
        summary = _run_job_body(args)

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
