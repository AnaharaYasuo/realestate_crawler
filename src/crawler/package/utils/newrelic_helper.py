import logging
import os

logger = logging.getLogger(__name__)


def init_new_relic() -> bool:
    """Initialize New Relic APM agent if NEW_RELIC_LICENSE_KEY is configured in the environment."""
    license_key = os.getenv("NEW_RELIC_LICENSE_KEY")
    if not license_key:
        return False

    app_name = os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")

    try:
        import newrelic.agent

        newrelic.agent.initialize()
        logger.info(f"New Relic APM agent initialized successfully for application: {app_name}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to initialize New Relic APM agent: {e}")
        return False
