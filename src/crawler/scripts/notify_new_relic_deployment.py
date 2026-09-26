#!/usr/bin/env python3
"""
New Relic Change Tracking Deployment Notification Script.
Notifies New Relic of application deployments to track performance impact.
"""
import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Setup environment path dynamically
_current_dir = os.path.dirname(os.path.abspath(__file__))
_crawler_root = os.path.dirname(_current_dir)
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

try:
    import setup_env
    setup_env.init_environment()
except ImportError:
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NERDGRAPH_ENDPOINTS: dict[str, str] = {
    "us": "https://api.newrelic.com/graphql",
    "eu": "https://api.eu.newrelic.com/graphql",
}
DEFAULT_TIMEOUT_SEC = 10.0


def get_nerdgraph_endpoint(region: str = "us") -> str:
    """Retrieve the NerdGraph endpoint for the specified region."""
    return NERDGRAPH_ENDPOINTS.get(region.lower(), NERDGRAPH_ENDPOINTS["us"])


def create_deployment_payload(
    version: str,
    commit: str,
    changelog: str = "",
    user: str = "",
    entity_guid: str | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Build GraphQL payload for changeTrackingCreateDeployment mutation."""
    mutation = """
    mutation CreateDeployment($deployment: ChangeTrackingDeploymentInput!) {
      changeTrackingCreateDeployment(deployment: $deployment) {
        deploymentId
        entityGuid
      }
    }
    """
    deployment_input: dict[str, Any] = {
        "version": version,
        "commit": commit,
    }
    if changelog:
        deployment_input["changelog"] = changelog
        deployment_input["description"] = changelog
    if user:
        deployment_input["user"] = user
    if entity_guid:
        deployment_input["entityGuid"] = entity_guid
    if timestamp:
        deployment_input["timestamp"] = timestamp

    return {
        "query": mutation,
        "variables": {
            "deployment": deployment_input,
        },
    }


def send_nerdgraph_request(
    payload: dict[str, Any],
    api_key: str,
    endpoint: str = NERDGRAPH_ENDPOINTS["us"],
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Execute GraphQL query against New Relic NerdGraph API with finite timeout across socket reads."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "API-Key": api_key,
            "User-Agent": "RealEstate-DeploymentNotifier/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def notify_deployment(
    version: str,
    commit: str,
    changelog: str = "",
    user: str = "",
    entity_guid: str | None = None,
    region: str = "us",
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> bool:
    """Notify New Relic of a deployment event."""
    key = api_key or os.getenv("NEW_RELIC_API_KEY")
    if not key:
        logger.warning("NEW_RELIC_API_KEY not configured. Skipping deployment notification.")
        return False

    guid = entity_guid or os.getenv("NEW_RELIC_ENTITY_GUID")
    if not guid:
        logger.error("entity_guid is required for changeTrackingCreateDeployment (pass via --entity-guid or NEW_RELIC_ENTITY_GUID).")
        return False

    endpoint = get_nerdgraph_endpoint(region)
    payload = create_deployment_payload(
        version=version,
        commit=commit,
        changelog=changelog,
        user=user,
        entity_guid=guid,
    )

    try:
        res = send_nerdgraph_request(payload, key, endpoint=endpoint, timeout=timeout)
        if res.get("errors"):
            logger.error(f"NerdGraph returned errors: {res['errors']}")
            return False

        data = res.get("data")
        if not isinstance(data, dict):
            logger.error(f"Missing or invalid data field in NerdGraph response: {res}")
            return False

        dep_info = data.get("changeTrackingCreateDeployment")
        if not isinstance(dep_info, dict) or not dep_info.get("deploymentId"):
            logger.error(f"Deployment record failed or deploymentId missing: {res}")
            return False

        dep_id = dep_info["deploymentId"]
        logger.info(f"Successfully recorded deployment to New Relic! Deployment ID: {dep_id}")
        return True
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error from New Relic API ({e.code}): {e.reason}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to send deployment notification: {e}")
        return False


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Notify New Relic of deployment event (Change Tracking)")
    parser.add_argument("--version", required=True, help="Release version (e.g. v1.2.0)")
    parser.add_argument("--commit", required=True, help="Git commit SHA")
    parser.add_argument("--changelog", default="", help="Release notes or description")
    parser.add_argument("--user", default="github-actions", help="Deployer user or service")
    parser.add_argument("--entity-guid", default=os.getenv("NEW_RELIC_ENTITY_GUID"), help="Target entity GUID")
    parser.add_argument("--region", default=os.getenv("NEW_RELIC_REGION", "us"), choices=["us", "eu"], help="New Relic Region (us or eu)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SEC, help="Request timeout (max 10s)")

    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    timeout = min(args.timeout, 10.0)

    success = notify_deployment(
        version=args.version,
        commit=args.commit,
        changelog=args.changelog,
        user=args.user,
        entity_guid=args.entity_guid,
        region=args.region,
        timeout=timeout,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
