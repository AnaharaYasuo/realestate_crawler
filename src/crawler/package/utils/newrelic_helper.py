import logging
import os
import sys
import threading
from typing import Any

try:
    import newrelic.agent
except ImportError:
    newrelic = None

logger = logging.getLogger(__name__)

# Holds the Application object returned by register_application().
# Used to pass application= to record_custom_event() in batch/job processes.
_NR_APP: Any = None


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

        # register_application is required for batch processes that have no web transactions.
        # Without it, record_custom_event() outside a transaction is silently discarded (Issue #562 #2).
        # The returned Application object is stored globally so _get_application() returns it
        # to all record_custom_event() calls (CodeRabbit: must use returned object, not agent.application()).
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
    """Flush and shut down the New Relic agent before process exit.

    Must be called at the end of batch/job processes to ensure all buffered
    custom events (CrawlerExecution, ContainerSample, LlmEvent) are flushed
    to New Relic before the container terminates (Issue #562 #2).
    """
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

        # application= required outside a web transaction (batch/job processes) — Issue #562 #2
        agent.record_custom_event("LlmEvent", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic LLM event: {e}")
        return False


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

        # application= required outside a web transaction (batch/job processes) — Issue #562 #2
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
                with open(usage_file, "r") as f:
                    usage_bytes = int(f.read().strip())
                with open(limit_file, "r") as f:
                    limit_val = f.read().strip()
                return usage_bytes, (0 if limit_val == "max" else int(limit_val))
            except Exception:
                pass
    return 0, 0


def _read_cgroup_cpu() -> int:
    """Read CPU usage usec from cgroup v2 (cpu.stat) or v1 (cpuacct.usage)."""
    if os.path.exists("/sys/fs/cgroup/cpu.stat"):
        try:
            with open("/sys/fs/cgroup/cpu.stat", "r") as f:
                for line in f:
                    if line.startswith("usage_usec"):
                        return int(line.split()[1])
        except Exception:
            pass
    elif os.path.exists("/sys/fs/cgroup/cpu/cpuacct.usage"):
        try:
            with open("/sys/fs/cgroup/cpu/cpuacct.usage", "r") as f:
                return int(int(f.read().strip()) / 1000)
        except Exception:
            pass
    return 0


def record_container_sample(
    service_name: str | None = None,
    custom_metrics: dict[str, Any] | None = None,
) -> bool:
    """Record container CPU and memory resource consumption to New Relic (ContainerSample)."""
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return False

    try:
        agent = _get_agent()
        if agent is None:
            return False

        app_name = service_name or os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")
        params: dict[str, Any] = dict(custom_metrics) if custom_metrics else {}

        mem_usage_bytes, mem_limit_bytes = _read_cgroup_memory()
        cpu_usage_usec = _read_cgroup_cpu()

        mem_usage_mb = round(mem_usage_bytes / (1024 * 1024), 2) if mem_usage_bytes > 0 else 0.0
        mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2) if mem_limit_bytes > 0 else 0.0
        mem_percent = round((mem_usage_bytes / mem_limit_bytes) * 100, 2) if mem_limit_bytes > 0 else 0.0
        cpu_usage_seconds = round(cpu_usage_usec / 1_000_000, 2) if cpu_usage_usec > 0 else 0.0

        params.update({
            "containerName": app_name,
            "containerId": os.getenv("HOSTNAME", "unknown"),
            "memoryUsageBytes": mem_usage_bytes,
            "memoryUsageMb": mem_usage_mb,
            "memoryLimitBytes": mem_limit_bytes,
            "memoryLimitMb": mem_limit_mb,
            "memoryPercent": mem_percent,
            "cpuUsageUsec": cpu_usage_usec,
            "cpuUsageSeconds": cpu_usage_seconds,
        })

        # application= required outside a web transaction (batch/job processes) — Issue #562 #3
        agent.record_custom_event("ContainerSample", params, application=_get_application())
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic container sample: {e}")
        return False


def start_container_sample_thread(interval_sec: int = 60, service_name: str | None = None) -> threading.Thread | None:
    """Start a background thread that records ContainerSample every interval_sec seconds.

    Required for batch/job processes to capture memory usage throughout execution,
    not just at startup (Issue #562 #3). Returns the daemon thread (already started).
    """
    if not os.getenv("NEW_RELIC_LICENSE_KEY"):
        return None

    stop_event = threading.Event()

    def _sampler() -> None:
        while not stop_event.wait(timeout=interval_sec):
            try:
                record_container_sample(service_name=service_name)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"ContainerSample thread error: {e}")

    t = threading.Thread(target=_sampler, daemon=True, name="nr-container-sample")
    t.start()
    return t
