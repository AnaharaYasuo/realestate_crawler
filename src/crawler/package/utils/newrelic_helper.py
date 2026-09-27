import logging
import os
import sys
from typing import Any

try:
    import newrelic.agent
except ImportError:
    newrelic = None

logger = logging.getLogger(__name__)


def _get_agent() -> Any | None:
    """Safely obtain newrelic.agent or mock from sys.modules."""
    if "newrelic.agent" in sys.modules:
        return sys.modules["newrelic.agent"]
    if "newrelic" in sys.modules and hasattr(sys.modules["newrelic"], "agent"):
        return sys.modules["newrelic"].agent
    if newrelic is not None and hasattr(newrelic, "agent"):
        return newrelic.agent
    return None


def init_new_relic() -> bool:
    """Initialize New Relic APM agent if NEW_RELIC_LICENSE_KEY is configured in the environment."""
    license_key = os.getenv("NEW_RELIC_LICENSE_KEY")
    if not license_key:
        return False

    app_name = os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")

    try:
        agent = _get_agent()
        if agent is None:
            logger.warning("New Relic package not installed or agent unavailable")
            return False
        agent.initialize()
        logger.info(f"New Relic APM agent initialized successfully for application: {app_name}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to initialize New Relic APM agent: {e}")
        return False


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

        agent.record_custom_event("LlmEvent", params)
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

        agent.record_custom_event("CrawlerExecution", params)
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

        # 1. Read cgroup memory if running in Linux container
        mem_usage_bytes = 0
        mem_limit_bytes = 0
        for usage_file in ["/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"]:
            if os.path.exists(usage_file):
                try:
                    with open(usage_file, "r") as f:
                        mem_usage_bytes = int(f.read().strip())
                    break
                except Exception:
                    pass

        for limit_file in ["/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"]:
            if os.path.exists(limit_file):
                try:
                    with open(limit_file, "r") as f:
                        val = f.read().strip()
                        if val != "max":
                            mem_limit_bytes = int(val)
                    break
                except Exception:
                    pass

        mem_usage_mb = round(mem_usage_bytes / (1024 * 1024), 2) if mem_usage_bytes > 0 else 0.0
        mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2) if mem_limit_bytes > 0 else 0.0
        mem_percent = round((mem_usage_bytes / mem_limit_bytes) * 100, 2) if mem_limit_bytes > 0 else 0.0

        params.update({
            "containerName": app_name,
            "containerId": os.getenv("HOSTNAME", "unknown"),
            "memoryUsageBytes": mem_usage_bytes,
            "memoryUsageMb": mem_usage_mb,
            "memoryLimitBytes": mem_limit_bytes,
            "memoryLimitMb": mem_limit_mb,
            "memoryPercent": mem_percent,
        })

        agent.record_custom_event("ContainerSample", params)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to record New Relic container sample: {e}")
        return False
