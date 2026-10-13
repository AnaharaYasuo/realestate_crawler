"""
Resource limiter and dynamic concurrency calculation based on available machine/container memory (Issue #895).
"""
import logging
import os

logger = logging.getLogger(__name__)


def _read_cgroup_limit_mb() -> int | None:
    """Read memory limit in MB from cgroup v2 or v1."""
    limit_files = (
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    )
    for limit_file in limit_files:
        if not os.path.exists(limit_file):
            continue
        try:
            with open(limit_file, "r", encoding="utf-8") as f:
                val = f.read().strip()
            if val and val != "max":
                limit_bytes = int(val)
                if 0 < limit_bytes < (1024**4):
                    return int(limit_bytes / (1024 * 1024))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed reading {limit_file}: {e}")
    return None


def _read_proc_meminfo_mb() -> int | None:
    """Read available or total memory in MB from /proc/meminfo."""
    if not os.path.exists("/proc/meminfo"):
        return None
    try:
        mem_info = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    if val.isdigit():
                        mem_info[key] = int(val)
        if "MemAvailable" in mem_info:
            return int(mem_info["MemAvailable"] / 1024)
        if "MemTotal" in mem_info:
            return int(mem_info["MemTotal"] / 1024)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed reading /proc/meminfo: {e}")
    return None


def _read_sysconf_mb() -> int | None:
    """Read total physical memory in MB from os.sysconf."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return int((pages * page_size) / (1024 * 1024))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed reading os.sysconf: {e}")
    return None


def detect_available_memory_mb() -> int | None:
    """
    Detect available or limit memory in MB for the current container / host environment.
    Checks cgroup v2/v1 memory limits, /proc/meminfo, and os.sysconf.
    Returns memory in MB, or None if undetermined.
    """
    cgroup_mb = _read_cgroup_limit_mb()
    if cgroup_mb is not None:
        return cgroup_mb

    proc_mb = _read_proc_meminfo_mb()
    if proc_mb is not None:
        return proc_mb

    return _read_sysconf_mb()


def get_resource_aware_concurrency(
    default_parallel: int = 9,
    default_playwright_parallel: int = 3,
) -> tuple[int, int, str]:
    """
    Calculate safe concurrency levels based on available memory and environment variables.
    Returns:
        (parallel, playwright_parallel, reason_str)
    """
    raw_parallel = os.getenv("CRAWLER_PARALLEL")
    raw_pw_parallel = os.getenv("CRAWLER_PLAYWRIGHT_PARALLEL")

    has_env_parallel = bool(raw_parallel and raw_parallel.isdigit() and int(raw_parallel) > 0)
    has_env_pw_parallel = bool(raw_pw_parallel and raw_pw_parallel.isdigit() and int(raw_pw_parallel) >= 0)

    avail_mb = detect_available_memory_mb()

    # Determine safe defaults from resource limits
    if avail_mb is not None:
        if avail_mb <= 4096:
            safe_p = 3
            safe_pw = 1
            tier = "LowMemory (<=4GB)"
        elif avail_mb <= 8192:
            safe_p = 5
            safe_pw = 2
            tier = "MediumMemory (<=8GB)"
        else:
            safe_p = default_parallel
            safe_pw = default_playwright_parallel
            tier = "HighMemory (>8GB)"
    else:
        safe_p = default_parallel
        safe_pw = default_playwright_parallel
        tier = "Undetermined"

    p = int(raw_parallel) if has_env_parallel else safe_p
    pw = int(raw_pw_parallel) if has_env_pw_parallel else safe_pw

    if has_env_parallel or has_env_pw_parallel:
        reason = f"Detected available memory: {avail_mb}MB ({tier}), but overridden by environment variables (parallel={p}, playwright_parallel={pw})"
    else:
        reason = f"Detected available memory: {avail_mb}MB ({tier}). Applied safe concurrency (parallel={p}, playwright_parallel={pw})"

    return p, pw, reason
