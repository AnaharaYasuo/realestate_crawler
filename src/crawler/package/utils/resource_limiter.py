"""
Resource limiter and dynamic concurrency calculation based on available machine/container memory (Issue #895).
"""
import logging
import os

from package.utils.crawl_jobs import is_cloud_environment

logger = logging.getLogger(__name__)


def _read_int_from_file(file_path: str) -> int | None:
    """Read single integer from file if exists, else None."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            val = f.read().strip()
        if val and val != "max" and val.isdigit():
            return int(val)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed reading {file_path}: {e}")
    return None


def _read_cgroup_limit_mb() -> int | None:
    """Read remaining available memory in MB under cgroup limits (limit - current usage)."""
    limit_usage_pairs = (
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
        ("/sys/fs/cgroup/memory/memory.limit_in_bytes", "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
    )
    for limit_file, usage_file in limit_usage_pairs:
        limit_bytes = _read_int_from_file(limit_file)
        if limit_bytes is not None and 0 < limit_bytes < (1024**4):
            usage_bytes = _read_int_from_file(usage_file)
            if usage_bytes is not None:
                avail_bytes = max(0, limit_bytes - usage_bytes)
                return int(avail_bytes / (1024 * 1024))
    return None


def _read_proc_meminfo_mb() -> int | None:
    """Read available or total memory in MB from /proc/meminfo."""
    if not os.path.exists("/proc/meminfo"):
        return None
    try:
        mem_info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
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
    Detect available memory in MB for the current container / host environment.
    Takes the minimum of cgroup remaining memory and host available memory.
    """
    candidates = []
    cgroup_mb = _read_cgroup_limit_mb()
    if cgroup_mb is not None:
        candidates.append(cgroup_mb)

    proc_mb = _read_proc_meminfo_mb()
    if proc_mb is not None:
        candidates.append(proc_mb)

    if not candidates:
        sysconf_mb = _read_sysconf_mb()
        if sysconf_mb is not None:
            candidates.append(sysconf_mb)

    return min(candidates) if candidates else None


def _resolve_concurrency_env() -> tuple[int | None, int | None]:
    """Resolve parallel and playwright parallel from environment variables."""
    if is_cloud_environment():
        raw_p = os.getenv("CLOUD_CRAWLER_PARALLEL") or os.getenv("CRAWLER_PARALLEL")
        raw_pw = os.getenv("CLOUD_CRAWLER_PLAYWRIGHT_PARALLEL") or os.getenv("CRAWLER_PLAYWRIGHT_PARALLEL")
    else:
        raw_p = os.getenv("LOCAL_CRAWLER_PARALLEL") or os.getenv("CRAWLER_PARALLEL")
        raw_pw = os.getenv("LOCAL_CRAWLER_PLAYWRIGHT_PARALLEL") or os.getenv("CRAWLER_PLAYWRIGHT_PARALLEL")

    p = int(raw_p) if (raw_p and raw_p.isdigit() and int(raw_p) > 0) else None
    pw = int(raw_pw) if (raw_pw and raw_pw.isdigit() and int(raw_pw) >= 0) else None
    return p, pw


def _determine_memory_tier_defaults(
    avail_mb: int | None,
    default_p: int,
    default_pw: int,
) -> tuple[int, int, str]:
    """Determine safe default concurrency and tier name based on available memory."""
    if avail_mb is None:
        return default_p, default_pw, "Undetermined"
    if avail_mb < 512:
        return 0, 0, "CriticalMemory (<512MB)"
    if avail_mb <= 4096:
        return 3, 1, "LowMemory (<=4GB)"
    if avail_mb <= 8192:
        return 5, 2, "MediumMemory (<=8GB)"
    return default_p, default_pw, "HighMemory (>8GB)"


def get_resource_aware_concurrency(
    default_parallel: int = 7,
    default_playwright_parallel: int = 3,
) -> tuple[int, int, str]:
    """
    Calculate safe concurrency levels based on available memory and environment variables.
    Returns:
        (parallel, playwright_parallel, reason_str)
    """
    env_p, env_pw = _resolve_concurrency_env()
    avail_mb = detect_available_memory_mb()
    safe_p, safe_pw, tier = _determine_memory_tier_defaults(
        avail_mb, default_parallel, default_playwright_parallel
    )

    p = env_p if env_p is not None else safe_p
    pw = env_pw if env_pw is not None else safe_pw

    if env_p is not None or env_pw is not None:
        reason = f"Detected available memory: {avail_mb}MB ({tier}), but overridden by environment variables (parallel={p}, playwright_parallel={pw})"
    else:
        reason = f"Detected available memory: {avail_mb}MB ({tier}). Applied safe concurrency (parallel={p}, playwright_parallel={pw})"

    return p, pw, reason
