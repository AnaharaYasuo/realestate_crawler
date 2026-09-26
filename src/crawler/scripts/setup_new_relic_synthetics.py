import json
import logging
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NERDGRAPH_ENDPOINT = "https://api.newrelic.com/graphql"


def run_nerdgraph_query(api_key: str, query: str, variables: dict | None = None) -> dict:
    """Execute GraphQL query against New Relic NerdGraph."""
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "realestate-crawler-synthetics-setup/1.0",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    req = urllib.request.Request(
        NERDGRAPH_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error(f"HTTP {e.code} error from NerdGraph: {error_body}")
        raise
    except Exception as e:
        logger.error(f"Failed to communicate with NerdGraph: {e}")
        raise


def get_existing_monitors(api_key: str, account_id: int) -> list:
    """List existing Synthetics monitors for the given account."""
    query = """
    query GetSyntheticsMonitors($searchQuery: String!) {
      actor {
        entitySearch(query: $searchQuery) {
          results {
            entities {
              name
              guid
              type
              ... on SyntheticMonitorEntityOutline {
                monitorType
                monitoredUrl
                period
              }
            }
          }
        }
      }
    }
    """
    search_query = f"type = 'MONITOR' AND domain = 'SYNTH' AND accountId = {account_id}"
    res = run_nerdgraph_query(api_key, query, {"searchQuery": search_query})
    if res.get("errors"):
        raise RuntimeError(f"NerdGraph list query failed: {res['errors']}")
    data = res.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("NerdGraph list response does not contain data")
    entities = data.get("actor", {}).get("entitySearch", {}).get("results", {}).get("entities", [])
    return entities


def create_or_verify_synthetics_monitor(
    api_key: str,
    account_id: int,
    target_url: str,
    monitor_name: str = "RealEstate API Health Check",
) -> dict:
    """Create Synthetics Simple Monitor if not present, or return existing one."""
    logger.info(f"Checking existing Synthetics monitors for account {account_id}...")
    existing = get_existing_monitors(api_key, account_id)
    for m in existing:
        if m.get("name") == monitor_name:
            logger.info(f"Synthetics monitor '{monitor_name}' already exists: GUID={m.get('guid')}")
            return m

    logger.info(f"Creating new Synthetics Simple Monitor: {monitor_name} -> {target_url}")
    mutation = """
    mutation CreateMonitor($accountId: Int!, $monitor: SyntheticsCreateSimpleMonitorInput!) {
      syntheticsCreateSimpleMonitor(accountId: $accountId, monitor: $monitor) {
        errors {
          description
          type
        }
        monitor {
          id
          name
          status
          period
          uri
        }
      }
    }
    """
    variables = {
        "accountId": account_id,
        "monitor": {
            "name": monitor_name,
            "status": "ENABLED",
            "period": "EVERY_5_MINUTES",
            "uri": target_url,
            "locations": {
                "public": ["AP_NORTHEAST_1", "AP_EAST_1"],
            },
        },
    }

    res = run_nerdgraph_query(api_key, mutation, variables)
    data = res.get("data", {}).get("syntheticsCreateSimpleMonitor", {})
    errors = data.get("errors") or res.get("errors")
    if errors:
        raise RuntimeError(f"Failed to create Synthetics monitor: {errors}")

    created = data.get("monitor", {})
    logger.info(f"Synthetics monitor created successfully: {created}")
    return created


def main():
    load_dotenv()
    api_key = os.getenv("NEW_RELIC_API_KEY")
    account_id_str = os.getenv("NEW_RELIC_ACCOUNT_ID")
    target_url = os.getenv("HEALTHCHECK_URL")

    if not api_key:
        logger.error("NEW_RELIC_API_KEY is not set in environment or .env")
        sys.exit(1)
    if not account_id_str:
        logger.error("NEW_RELIC_ACCOUNT_ID is not set in environment or .env")
        sys.exit(1)
    if not target_url:
        logger.error("HEALTHCHECK_URL is not set in environment or .env")
        sys.exit(1)

    try:
        account_id = int(account_id_str)
    except ValueError:
        logger.error(f"Invalid NEW_RELIC_ACCOUNT_ID: {account_id_str}")
        sys.exit(1)

    try:
        res = create_or_verify_synthetics_monitor(
            api_key=api_key,
            account_id=account_id,
            target_url=target_url,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        sys.exit(0)
    except Exception:
        logger.exception("Error setting up New Relic Synthetics monitor")
        sys.exit(1)


if __name__ == "__main__":
    main()
