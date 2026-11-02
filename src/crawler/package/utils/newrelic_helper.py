import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Any

try:
    import newrelic.agent
except ImportError:
    newrelic = None

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

logger = logging.getLogger(__name__)

# Holds the Application object returned by register_application().
# Used to pass application= to record_custom_event() in batch/job processes.
_NR_APP: Any = None

# Baseline for delta CPU% calculation across calls
_cpu_sample_lock = threading.Lock()
_last_proc_cpu_time: float | None = None
_last_proc_wall_time: float | None = None

# Baseline for delta Network rate calculation across calls
_net_sample_lock = threading.Lock()
_last_net_bytes_recv: int | None = None
_last_net_bytes_sent: int | None = None
_last_net_wall_time: float | None = None


def _get_agent() -> Any | None:
    """Safely obtain newrelic.agent or mock from sys.modules."""
    if "newrelic.agent" in sys.modules:
        return sys.modules["newrelic.agent"]
    if "newrelic" in sys.modules and hasattr(sys.modules["newrelic"], "agent"):
        return sys.modules["newrelic"].agent
    if newrelic is not None and hasattr(newrelic, "agent"):
        return newrelic.agent
    return None


def _get_application() -> Any | None:
    """Return the registered New Relic Application object, or None if not initialized."""
    return _NR_APP


def init_new_relic() -> bool:
    """Initialize New Relic APM agent and register application for batch/job processes.

    Calls register_application(timeout=10) so that record_custom_event() outside
    a transaction can specify application= and actually deliver events.
    APM log forwarding is disabled to prevent double-ingestion from Cloud Logging.
    """
    license_key = os.getenv("NEW_RELIC_LICENSE_KEY", "").strip()
    if not license_key:
        return False
    # Write back stripped key so the agent picks it up correctly (Issue #529, #562 #9)
    os.environ["NEW_RELIC_LICENSE_KEY"] = license_key

    app_name = os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")

    try:
        agent = _get_agent()
        if agent is None:
            logger.warning("New Relic package not installed or agent unavailable")
            return False

        # Disable APM log forwarding — logs flow via Cloud Logging → Pub/Sub (Issue #562 #9)
        agent.initialize(config_file=None, environment=None, ignore_errors=True)

        global _NR_APP
        _NR_APP = agent.register_application(name=app_name, timeout=10.0)
        if _NR_APP is None:
            logger.warning("New Relic register_application returned None — events may not be delivered")
        logger.info(f"New Relic APM agent initialized and registered for application: {app_name}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to initialize New Relic APM agent: {e}")
        return False


def shutdown_new_relic(timeout: float = 10.0) -> None:
    """Flush and shut down the New Relic agent before process exit."""
    agent = _get_agent()
    if agent is None:
        return
    try:
        agent.shutdown_agent(timeout=timeout)
        logger.info("New Relic agent shut down and events flushed.")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"New Relic shutdown_agent failed: {e}")


def record_llm_event(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    status: str = "success",
    error_msg: str | None = None,
    cost_usd: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record LLM/GenAI invocation telemetry to New Relic custom events (LlmEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        total_tokens = prompt_tokens + completion_tokens
        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "duration_ms": duration_ms,
            "status": status,
        })
        if cost_usd is not None:
            params["cost_usd"] = cost_usd
        if error_msg:
            params["error_msg"] = error_msg

        agent.record_custom_event("LlmEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic LLM event: {e}")
        return False



def _get_current_concurrency_attributes(company: str | None = None) -> dict[str, Any]:
    """Extract current job parallel, playwright parallel, and detail concurrency safely."""
    from package.utils.resource_limiter import get_resource_aware_concurrency
    from package.api.adaptive_concurrency import AdaptiveConcurrencyController

    p, pw, _ = get_resource_aware_concurrency()
    active_jobs = AdaptiveConcurrencyController.get_active_jobs_count()
    detail_c = AdaptiveConcurrencyController.get_effective_concurrency(company=company, active_jobs=active_jobs)

    return {
        "parallel": p,
        "playwright_parallel": pw,
        "detail_concurrency": detail_c,
        "active_jobs_count": active_jobs,
    }


def record_crawler_metrics(
    site_name: str,
    property_type: str,
    count: int,
    duration_sec: float,
    zero_count: bool = False,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record crawler execution metrics to New Relic custom events (CrawlerExecution)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        items_per_sec = (count / duration_sec) if duration_sec > 0 else 0.0
        params: dict[str, Any] = dict(metadata) if metadata else {}
        try:
            concurrency_attrs = _get_current_concurrency_attributes(company=site_name)
            for k in ("parallel", "playwright_parallel", "detail_concurrency", "active_jobs_count"):
                if k not in params and k in concurrency_attrs:
                    params[k] = concurrency_attrs[k]
        except Exception as e:
            logger.warning(f"Failed to append concurrency attributes to CrawlerExecution: {e}")

        params.update({
            "site_name": site_name,
            "property_type": property_type,
            "count": count,
            "item_count": count,
            "duration_sec": duration_sec,
            "items_per_sec": items_per_sec,
            "zero_count": zero_count or (count == 0 and status != "no_updates"),
            "status": status,
        })

        agent.record_custom_event("CrawlerExecution", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic crawler execution metrics: {e}")
        return False


def notice_error(error: Exception, custom_params: dict[str, Any] | None = None) -> bool:
    """Safely report exception to New Relic APM with custom attributes."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False
        params = custom_params or {}
        agent.notice_error(error, parameters=params)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to report error to New Relic: {e}")
        return False


def _read_cgroup_memory() -> tuple[int, int]:
    """Read memory usage and limit bytes from cgroup v2 or v1."""
    for usage_file, limit_file in [
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"),
        ("/sys/fs/cgroup/memory/memory.usage_in_bytes", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ]:
        if os.path.exists(usage_file) and os.path.exists(limit_file):
            try:
                with open(usage_file) as f:
                    usage_bytes = int(f.read().strip())
                with open(limit_file) as f:
                    limit_val = f.read().strip()
                return usage_bytes, (0 if limit_val == "max" else int(limit_val))
            except Exception:
                pass
    return 0, 0


def _read_cgroup_cpu() -> int:
    """Read CPU usage usec from cgroup v2 (cpu.stat) or v1 (cpuacct.usage)."""
    if os.path.exists("/sys/fs/cgroup/cpu.stat"):
        try:
            with open("/sys/fs/cgroup/cpu.stat") as f:
                for line in f:
                    if line.startswith("usage_usec"):
                        return int(line.split()[1])
        except Exception:
            pass
    elif os.path.exists("/sys/fs/cgroup/cpu/cpuacct.usage"):
        try:
            with open("/sys/fs/cgroup/cpu/cpuacct.usage") as f:
                return int(int(f.read().strip()) / 1000)
        except Exception:
            pass
    return 0


def _read_psutil_memory(pid: int) -> tuple[int, int, float] | None:
    if _psutil is None:
        return None
    try:
        proc = _psutil.Process(pid)
        rss = int(proc.memory_info().rss)
        for child in proc.children(recursive=True):
            try:
                rss += int(child.memory_info().rss)
            except Exception:
                pass
        vm = _psutil.virtual_memory()
        return rss, int(vm.total), round(float(vm.percent), 2)
    except Exception:
        return None


def _read_procfs_memory(pid: int) -> tuple[int, int, float] | None:
    if not (os.path.exists(f"/proc/{pid}/statm") and os.path.exists("/proc/meminfo")):
        return None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        with open(f"/proc/{pid}/statm") as f:
            parts = f.read().split()
            rss_bytes = int(parts[1]) * page_size if len(parts) > 1 else 0
        mem_total = 0
        mem_avail = 0
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1]) * 1024
        sys_pct = round(((mem_total - mem_avail) / mem_total) * 100.0, 2) if mem_total > 0 else 0.0
        return rss_bytes, mem_total, sys_pct
    except Exception:
        return None


class _WinMemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _WinProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _read_win32_memory(pid: int) -> tuple[int, int, float] | None:
    if sys.platform != "win32":
        return None
    try:
        stat = _WinMemoryStatusEx()
        stat.dwLength = ctypes.sizeof(_WinMemoryStatusEx)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total_phys = int(stat.ullTotalPhys)
        sys_pct = float(stat.dwMemoryLoad)

        pmc = _WinProcessMemoryCounters()
        pmc.cb = ctypes.sizeof(_WinProcessMemoryCounters)
        h_proc = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
        rss_bytes = 0
        if h_proc:
            try:
                if ctypes.windll.psapi.GetProcessMemoryInfo(h_proc, ctypes.byref(pmc), ctypes.sizeof(pmc)):
                    rss_bytes = int(pmc.WorkingSetSize)
            finally:
                ctypes.windll.kernel32.CloseHandle(h_proc)
        return rss_bytes, total_phys, round(sys_pct, 2)
    except Exception:
        return None


def _read_host_memory_fallback(target_pid: int | None = None) -> tuple[int, int, float]:
    """Read (process_rss_bytes, total_sys_bytes, sys_memory_percent) without requiring psutil."""
    pid = target_pid or os.getpid()
    for reader in (_read_psutil_memory, _read_procfs_memory, _read_win32_memory):
        res = reader(pid)
        if res is not None:
            return res
    return 0, 0, 0.0


def _get_load_avg_1m() -> float:
    if not hasattr(os, "getloadavg"):
        return 0.0
    try:
        return round(float(os.getloadavg()[0]), 2)
    except Exception:
        return 0.0


def _read_psutil_cpu(pid: int, cpu_usec: int, cpu_sec: float, load_avg_1m: float) -> dict[str, float] | None:
    if _psutil is None:
        return None
    try:
        proc = _psutil.Process(pid)
        return {
            "cpuUsageUsec": cpu_usec or int(cpu_sec * 1_000_000),
            "cpuUsageSeconds": cpu_sec,
            "cpuPercent": round(float(proc.cpu_percent(interval=None)), 2),
            "systemCpuPercent": round(float(_psutil.cpu_percent(interval=None)), 2),
            "loadAvg1m": load_avg_1m,
        }
    except Exception:
        return None


def _read_cpu_metrics(target_pid: int | None = None) -> dict[str, float]:
    """Read CPU usage seconds, process CPU %, system CPU %, and 1m load average."""
    global _last_proc_cpu_time, _last_proc_wall_time
    cpu_usec = _read_cgroup_cpu()
    cpu_sec = round(cpu_usec / 1_000_000, 2) if cpu_usec > 0 else round(time.process_time(), 2)
    load_avg_1m = _get_load_avg_1m()

    ps_res = _read_psutil_cpu(target_pid or os.getpid(), cpu_usec, cpu_sec, load_avg_1m)
    if ps_res is not None:
        return ps_res

    proc_cpu_pct = 0.0
    with _cpu_sample_lock:
        now_proc = time.process_time()
        now_wall = time.monotonic()
        if _last_proc_cpu_time is not None and _last_proc_wall_time is not None:
            dt_wall = now_wall - _last_proc_wall_time
            if dt_wall > 0.05:
                proc_cpu_pct = round(max(0.0, ((now_proc - _last_proc_cpu_time) / dt_wall) * 100.0), 2)
        _last_proc_cpu_time = now_proc
        _last_proc_wall_time = now_wall

    cpu_count = os.cpu_count() or 1
    ratio = (load_avg_1m / cpu_count) * 100.0 if load_avg_1m > 0 else (proc_cpu_pct / cpu_count)
    sys_cpu_pct = round(min(100.0, ratio), 2)

    return {
        "cpuUsageUsec": cpu_usec or int(cpu_sec * 1_000_000),
        "cpuUsageSeconds": cpu_sec,
        "cpuPercent": proc_cpu_pct,
        "systemCpuPercent": sys_cpu_pct,
        "loadAvg1m": load_avg_1m,
    }


_TCP_STATE_COUNTER_MAP = {
    "ESTABLISHED": "tcpEstablishedCount",
    "SYN_SENT": "tcpSynSentCount",
    "CLOSE_WAIT": "tcpCloseWaitCount",
    "TIME_WAIT": "tcpTimeWaitCount",
    "01": "tcpEstablishedCount",
    "02": "tcpSynSentCount",
    "06": "tcpTimeWaitCount",
    "08": "tcpCloseWaitCount",
}


def _increment_tcp_state(net_info: dict[str, Any], state_key: str) -> None:
    net_info["tcpTotalCount"] += 1
    counter_key = _TCP_STATE_COUNTER_MAP.get(state_key)
    if counter_key:
        net_info[counter_key] += 1


def _populate_psutil_network(pid: int, net_info: dict[str, Any]) -> bool:
    if _psutil is None:
        return False
    try:
        nio = _psutil.net_io_counters()
        if nio:
            net_info["netBytesSent"] = int(nio.bytes_sent)
            net_info["netBytesRecv"] = int(nio.bytes_recv)
            net_info["netPacketsSent"] = int(nio.packets_sent)
            net_info["netPacketsRecv"] = int(nio.packets_recv)
        conns = _psutil.Process(pid).net_connections(kind="tcp")
        endpoints: list[str] = []
        for c in conns:
            st = str(c.status).upper()
            _increment_tcp_state(net_info, st)
            if c.raddr:
                ep = f"{c.raddr.ip}:{c.raddr.port}({st})"
                if ep not in endpoints:
                    endpoints.append(ep)
        net_info["remoteEndpoints"] = endpoints[:15]
        return True
    except Exception:
        return False


def _populate_procfs_net_dev(net_info: dict[str, Any]) -> None:
    if not os.path.exists("/proc/net/dev"):
        return
    try:
        rx_bytes = tx_bytes = rx_pkts = tx_pkts = 0
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                if ":" not in line:
                    continue
                iface, data = line.split(":", 1)
                cols = data.split()
                if iface.strip() != "lo" and len(cols) >= 10:
                    rx_bytes += int(cols[0])
                    rx_pkts += int(cols[1])
                    tx_bytes += int(cols[8])
                    tx_pkts += int(cols[9])
        net_info["netBytesRecv"] = rx_bytes
        net_info["netPacketsRecv"] = rx_pkts
        net_info["netBytesSent"] = tx_bytes
        net_info["netPacketsSent"] = tx_pkts
    except Exception:
        pass


def _populate_procfs_net_tcp(net_info: dict[str, Any]) -> None:
    for tcp_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        if not os.path.exists(tcp_file):
            continue
        try:
            with open(tcp_file) as f:
                for line in f.readlines()[1:]:
                    cols = line.split()
                    if len(cols) >= 4:
                        _increment_tcp_state(net_info, cols[3].upper())
        except Exception:
            pass


def _populate_win32_netstat(pid: int, net_info: dict[str, Any]) -> None:
    if sys.platform != "win32" or net_info["tcpTotalCount"] > 0:
        return
    try:
        proc_res = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        pid_str = str(pid)
        endpoints: list[str] = []
        for line in (proc_res.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[4] == pid_str:
                state = parts[3].upper()
                _increment_tcp_state(net_info, state)
                ep = f"{parts[2]}({state})"
                if ep not in endpoints:
                    endpoints.append(ep)
        net_info["remoteEndpoints"] = endpoints[:15]
    except Exception:
        pass


def _read_network_metrics(target_pid: int | None = None) -> dict[str, Any]:
    """Read network I/O counters and active TCP socket state counts."""
    net_info: dict[str, Any] = {
        "netBytesSent": 0,
        "netBytesRecv": 0,
        "netPacketsSent": 0,
        "netPacketsRecv": 0,
        "tcpEstablishedCount": 0,
        "tcpSynSentCount": 0,
        "tcpCloseWaitCount": 0,
        "tcpTimeWaitCount": 0,
        "tcpTotalCount": 0,
        "remoteEndpoints": [],
    }
    pid = target_pid or os.getpid()
    if _populate_psutil_network(pid, net_info):
        return net_info
    _populate_procfs_net_dev(net_info)
    _populate_procfs_net_tcp(net_info)
    _populate_win32_netstat(pid, net_info)
    return net_info



def _calculate_network_rates(cur_recv: int, cur_sent: int) -> tuple[float, float]:
    """Calculate delta network receive and send rates in KB/s.

    Caller must hold _net_sample_lock to synchronize with baseline reads.
    """
    global _last_net_bytes_recv, _last_net_bytes_sent, _last_net_wall_time
    # If network counters are unavailable (both 0), preserve existing baseline to avoid spikes
    if cur_recv == 0 and cur_sent == 0:
        return 0.0, 0.0

    recv_rate_kbps = 0.0
    sent_rate_kbps = 0.0
    now_wall = time.monotonic()

    if _last_net_wall_time is not None and _last_net_bytes_recv is not None and _last_net_bytes_sent is not None:
        dt = now_wall - _last_net_wall_time
        if dt > 0.05:
            delta_recv = max(0, cur_recv - _last_net_bytes_recv)
            delta_sent = max(0, cur_sent - _last_net_bytes_sent)
            recv_rate_kbps = round((delta_recv / dt) / 1024.0, 2)
            sent_rate_kbps = round((delta_sent / dt) / 1024.0, 2)
    _last_net_bytes_recv = cur_recv
    _last_net_bytes_sent = cur_sent
    _last_net_wall_time = now_wall

    return recv_rate_kbps, sent_rate_kbps


def collect_hardware_resource_metrics(target_pid: int | None = None) -> dict[str, Any]:
    """Collect unified CPU, memory, network, thread, child-process, and DB metrics."""
    mem_usage_bytes, mem_limit_bytes = _read_cgroup_memory()
    host_rss_bytes, host_total_bytes, sys_mem_pct = _read_host_memory_fallback(target_pid=target_pid)

    if mem_usage_bytes <= 0:
        mem_usage_bytes = host_rss_bytes
    if mem_limit_bytes <= 0:
        mem_limit_bytes = host_total_bytes

    mem_usage_mb = round(mem_usage_bytes / (1024 * 1024), 2) if mem_usage_bytes > 0 else 0.0
    mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2) if mem_limit_bytes > 0 else 0.0
    mem_percent = round((mem_usage_bytes / mem_limit_bytes) * 100, 2) if mem_limit_bytes > 0 else 0.0
    if sys_mem_pct <= 0.0 and mem_percent > 0.0:
        sys_mem_pct = mem_percent

    cpu_data = _read_cpu_metrics(target_pid=target_pid)
    with _net_sample_lock:
        net_data = _read_network_metrics(target_pid=target_pid)
        recv_rate_kbps, sent_rate_kbps = _calculate_network_rates(
            net_data.get("netBytesRecv", 0),
            net_data.get("netBytesSent", 0),
        )
    net_data["netRecvRateKbps"] = recv_rate_kbps
    net_data["netSentRateKbps"] = sent_rate_kbps

    child_proc_count = 0
    if _psutil is not None:
        try:
            child_proc_count = len(_psutil.Process(target_pid or os.getpid()).children(recursive=True))
        except Exception:
            pass

    db_open = 0
    try:
        from django.db import connections

        db_open = sum(1 for alias in connections if connections[alias].connection is not None)
    except Exception:
        pass

    metrics: dict[str, Any] = {
        "memoryUsageBytes": mem_usage_bytes,
        "memoryUsageMb": mem_usage_mb,
        "memoryLimitBytes": mem_limit_bytes,
        "memoryLimitMb": mem_limit_mb,
        "memoryPercent": mem_percent,
        "systemMemoryPercent": sys_mem_pct,
        "activeThreadsCount": threading.active_count(),
        "childProcessCount": child_proc_count,
        "dbConnectionsOpen": db_open,
    }
    metrics.update(cpu_data)
    metrics.update(net_data)
    return metrics


def record_container_sample(
    service_name: str | None = None,
    custom_metrics: dict[str, Any] | None = None,
    *,
    emit_log: bool = True,
) -> bool:
    """Record CPU, memory, network, and DB resource consumption to logs and New Relic (ContainerSample)."""
    app_name = service_name or os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")
    params: dict[str, Any] = dict(custom_metrics) if custom_metrics else {}

    hw_metrics = collect_hardware_resource_metrics()
    # Exclude list objects from flat New Relic custom event attributes
    remote_endpoints = hw_metrics.pop("remoteEndpoints", [])
    if remote_endpoints:
        params["remoteEndpointsSample"] = ",".join(remote_endpoints[:8])

    params.update(hw_metrics)

    try:
        concurrency_attrs = _get_current_concurrency_attributes()
        for k, v in concurrency_attrs.items():
            if k not in params:
                params[k] = v
    except Exception as e:
        logger.warning(f"Failed to append concurrency attributes to ContainerSample: {e}")

    params.update({
        "containerName": app_name,
        "containerId": os.getenv("HOSTNAME", "unknown"),
    })

    if emit_log:
        logger.info(
            "[ResourceSample] service=%s cpu_proc=%.1f%% cpu_sys=%.1f%% mem=%.1fMB(%.1f%%) "
            "tcp_estab=%d tcp_total=%d net_rx=%dB net_tx=%dB db_open=%d threads=%d",
            app_name,
            params.get("cpuPercent", 0.0),
            params.get("systemCpuPercent", 0.0),
            params.get("memoryUsageMb", 0.0),
            params.get("memoryPercent", 0.0),
            params.get("tcpEstablishedCount", 0),
            params.get("tcpTotalCount", 0),
            params.get("netBytesRecv", 0),
            params.get("netBytesSent", 0),
            params.get("dbConnectionsOpen", 0),
            params.get("activeThreadsCount", 0),
        )

    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        # application= required outside a web transaction (batch/job processes) — Issue #562 #3
        agent.record_custom_event("ContainerSample", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic container sample: {e}")
        return False


def record_hang_diagnostic_event(snapshot: dict[str, Any]) -> bool:
    """Record a HangDiagnosticEvent to New Relic when a crawler job stalls or times out."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False
    try:
        agent = _get_agent()
        if agent is None:
            return False
        hw = snapshot.get("hardware_and_network", {})
        db = snapshot.get("database", {})
        params: dict[str, Any] = {
            "company": snapshot.get("company", ""),
            "property_type": snapshot.get("property_type", ""),
            "pid": snapshot.get("pid", 0),
            "reason": snapshot.get("reason", "HangSilentFailure"),
            "primary_target_url": str(snapshot.get("primary_target_url", ""))[:500],
            "primary_parent_list_url": str(snapshot.get("primary_parent_list_url", ""))[:500],
            "active_phases": ",".join(snapshot.get("active_phases", [])[:10])[:500],
            "cpuPercent": hw.get("cpuPercent", 0.0),
            "systemCpuPercent": hw.get("systemCpuPercent", 0.0),
            "memoryUsageMb": hw.get("memoryUsageMb", 0.0),
            "systemMemoryPercent": hw.get("systemMemoryPercent", 0.0),
            "tcpEstablishedCount": hw.get("tcpEstablishedCount", 0),
            "tcpSynSentCount": hw.get("tcpSynSentCount", 0),
            "tcpCloseWaitCount": hw.get("tcpCloseWaitCount", 0),
            "tcpTotalCount": hw.get("tcpTotalCount", 0),
            "dbConnectionsOpen": db.get("connections_open", 0),
            "dbProxySqlReachable": bool(db.get("proxysql_reachable", False)),
            "dbPingMs": db.get("proxysql_ping_ms") or -1.0,
            "activeThreadsCount": hw.get("activeThreadsCount", 0),
        }
        agent.record_custom_event("HangDiagnosticEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic HangDiagnosticEvent: {e}")
        return False


def start_container_sample_thread(interval_sec: int = 60, service_name: str | None = None) -> threading.Thread | None:
    """Start a background thread that logs and records ContainerSample every interval_sec seconds.

    Runs regardless of whether NEW_RELIC_LICENSE_KEY is set so structured resource logs
    are always emitted during job execution (Issue #1170).
    """
    stop_event = threading.Event()

    def _sampler() -> None:
        while not stop_event.wait(timeout=interval_sec):
            try:
                record_container_sample(service_name=service_name, emit_log=True)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"ContainerSample thread error: {e}")

    t = threading.Thread(target=_sampler, daemon=True, name="nr-container-sample")
    t.start()
    return t


def record_http_request(
    domain: str,
    method: str,
    status_code: int,
    duration_ms: float,
    response_bytes: int = 0,
    site_name: str | None = None,
    is_blocked: bool = False,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record outgoing HTTP scraping request telemetry to New Relic (HttpRequestEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "domain": domain,
            "method": method.upper(),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_bytes": response_bytes,
            "site_name": site_name or domain,
            "is_blocked": is_blocked or status_code in (403, 429),
        })
        agent.record_custom_event("HttpRequestEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic HTTP request event: {e}")
        return False


def record_database_operation(
    table_name: str,
    operation: str,
    duration_ms: float,
    row_count: int = 0,
    status: str = "success",
    error_msg: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record database bulk upsert / query telemetry to New Relic (DatabaseEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "table_name": table_name,
            "operation": operation.lower(),
            "duration_ms": duration_ms,
            "row_count": row_count,
            "status": status,
        })
        if error_msg:
            params["error_msg"] = error_msg
        agent.record_custom_event("DatabaseEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic Database event: {e}")
        return False


def record_parser_metrics(
    site_name: str,
    property_type: str,
    duration_ms: float,
    total_fields: int,
    extracted_fields: int,
    missing_fields: int,
    missing_ratio: float,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record parser DOM processing speed and field completeness to New Relic (ParserEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "site_name": site_name,
            "property_type": property_type,
            "duration_ms": duration_ms,
            "total_fields": total_fields,
            "extracted_fields": extracted_fields,
            "missing_fields": missing_fields,
            "missing_ratio": missing_ratio,
            "status": status,
        })
        agent.record_custom_event("ParserEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic Parser event: {e}")
        return False


def record_field_fill_rate_event(
    site_name: str,
    property_type: str,
    fill_rates: dict[str, float],
    item_count: int,
    low_fill_threshold: float = 0.5,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record per-field extraction fill-rate drift metrics to New Relic (FieldFillRateEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        degraded = sorted([f for f, rate in fill_rates.items() if rate < low_fill_threshold]) if item_count > 0 else []
        min_rate = min(fill_rates.values()) if fill_rates else 0.0

        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "site_name": site_name,
            "property_type": property_type,
            "item_count": item_count,
            "min_fill_rate": round(min_rate, 4),
            "degraded_fields": ",".join(degraded),
            "has_drift": bool(degraded),
        })
        for field_name, rate in fill_rates.items():
            params[f"fill_rate_{field_name}"] = round(float(rate), 4)

        agent.record_custom_event("FieldFillRateEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic FieldFillRateEvent: {e}")
        return False


def record_ml_inference_metrics(
    model_type: str,
    duration_ms: float,
    evaluated_count: int,
    bargain_count: int,
    skipped_count: int = 0,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record ML bulk inference performance and bargain detection to New Relic (MlInferenceEvent)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        params: dict[str, Any] = dict(metadata) if metadata else {}
        params.update({
            "model_type": model_type,
            "duration_ms": duration_ms,
            "evaluated_count": evaluated_count,
            "bargain_count": bargain_count,
            "skipped_count": skipped_count,
            "status": status,
        })
        agent.record_custom_event("MlInferenceEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic ML inference event: {e}")
        return False
