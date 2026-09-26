#!/usr/bin/env python3
"""
New Relic Alert Policies & NRQL Conditions Provisioner for Real Estate Crawler.
Provisions specialized alerts for crawler operations, zero-count errors, parser degradation, and blocked requests.
"""
import argparse
import json
import logging
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

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


def build_alert_policy_payload(account_id: int, policy_name: str) -> dict[str, Any]:
    """Build NerdGraph mutation to create or find an alert policy."""
    mutation = """
    mutation CreateAlertPolicy($accountId: Int!, $policy: AlertsPolicyInput!) {
      alertsPolicyCreate(accountId: $accountId, policy: $policy) {
        id
        name
      }
    }
    """
    return {
        "query": mutation,
        "variables": {
            "accountId": account_id,
            "policy": {
                "name": policy_name,
                "incidentPreference": "PER_CONDITION",
            },
        },
    }


def build_nrql_conditions(account_id: int, policy_id: int) -> list[dict[str, Any]]:
    """Define specialized NRQL conditions for crawler health and anomaly detection."""
    return [
        {
            "name": "Crawler Zero-Count Scraping Failure",
            "policyId": policy_id,
            "enabled": True,
            "nrql": {
                "query": "SELECT count(*) FROM CrawlerExecution WHERE zero_count = true OR (`count` = 0 AND status != 'no_updates') FACET site_name",
            },
            "terms": [
                {
                    "priority": "CRITICAL",
                    "operator": "ABOVE",
                    "threshold": 0,
                    "thresholdDuration": 300,
                    "thresholdOccurrences": "AT_LEAST_ONCE",
                }
            ],
            "valueFunction": "SINGLE_VALUE",
        },
        {
            "name": "Crawler Parser Latency Degradation (>1.0s/item)",
            "policyId": policy_id,
            "enabled": True,
            "nrql": {
                "query": "SELECT average(duration_sec / `count`) FROM CrawlerExecution WHERE `count` > 0 FACET site_name",
            },
            "terms": [
                {
                    "priority": "WARNING",
                    "operator": "ABOVE",
                    "threshold": 1.0,
                    "thresholdDuration": 600,
                    "thresholdOccurrences": "ALL",
                }
            ],
            "valueFunction": "SINGLE_VALUE",
        },
        {
            "name": "Target Portal Blocked (403/429 Spike)",
            "policyId": policy_id,
            "enabled": True,
            "nrql": {
                "query": "SELECT count(*) FROM CrawlerExecution WHERE status IN ('blocked_403', 'rate_limited_429') FACET site_name",
            },
            "terms": [
                {
                    "priority": "CRITICAL",
                    "operator": "ABOVE",
                    "threshold": 2,
                    "thresholdDuration": 300,
                    "thresholdOccurrences": "AT_LEAST_ONCE",
                }
            ],
            "valueFunction": "SINGLE_VALUE",
        },
        {
            "name": "Container High Memory Usage Warning",
            "policyId": policy_id,
            "enabled": True,
            "nrql": {
                "query": "SELECT average(memoryUsedBytes / memoryLimitBytes * 100) FROM ContainerSample WHERE containerName LIKE '%crawler%' FACET containerName",
            },
            "terms": [
                {
                    "priority": "WARNING",
                    "operator": "ABOVE",
                    "threshold": 85.0,
                    "thresholdDuration": 300,
                    "thresholdOccurrences": "ALL",
                }
            ],
            "valueFunction": "SINGLE_VALUE",
        },
    ]


def run_nerdgraph_query(
    payload: dict[str, Any],
    api_key: str,
    endpoint: str = NERDGRAPH_ENDPOINTS["us"],
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Execute NerdGraph query with finite timeout across socket operations."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "API-Key": api_key,
            "User-Agent": "RealEstate-CrawlerAlerts/1.0",
        },
        method="POST",
    )
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    finally:
        socket.setdefaulttimeout(old_timeout)


def find_existing_policy_id(
    account_id: int,
    policy_name: str,
    api_key: str,
    endpoint: str = NERDGRAPH_ENDPOINTS["us"],
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> int | None:
    """Check if an alert policy with the given name already exists. Fast-fails on query error."""
    query = """
    query SearchPolicies($accountId: Int!, $policyName: String!) {
      actor {
        account(id: $accountId) {
          alerts {
            policiesSearch(searchCriteria: {name: $policyName}) {
              policies {
                id
                name
              }
            }
          }
        }
      }
    }
    """
    payload = {"query": query, "variables": {"accountId": account_id, "policyName": policy_name}}
    res = run_nerdgraph_query(payload, api_key, endpoint=endpoint, timeout=timeout)
    if res.get("errors"):
        raise RuntimeError(f"NerdGraph policy lookup failed: {res['errors']}")

    data = res.get("data") or {}
    actor = data.get("actor") or {}
    account = actor.get("account") or {}
    alerts = account.get("alerts") or {}
    policies_search = alerts.get("policiesSearch") or {}
    policies = policies_search.get("policies") or []

    for pol in policies:
        if pol.get("name") == policy_name and pol.get("id"):
            return int(pol["id"])
    return None


def find_existing_condition_names(
    account_id: int,
    policy_id: int,
    api_key: str,
    endpoint: str = NERDGRAPH_ENDPOINTS["us"],
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> set[str]:
    """Fetch existing NRQL condition names for the policy to prevent duplicates."""
    condition_names: set[str] = set()
    cursor = None
    query = """
    query SearchConditions($accountId: Int!, $policyId: ID!, $cursor: String) {
      actor {
        account(id: $accountId) {
          alerts {
            nrqlConditionsSearch(searchCriteria: {policyId: $policyId}, cursor: $cursor) {
              nextCursor
              nrqlConditions {
                id
                name
              }
            }
          }
        }
      }
    }
    """
    while True:
        payload = {"query": query, "variables": {"accountId": account_id, "policyId": str(policy_id), "cursor": cursor}}
        res = run_nerdgraph_query(payload, api_key, endpoint=endpoint, timeout=timeout)
        if res.get("errors"):
            raise RuntimeError(f"NerdGraph condition lookup failed: {res['errors']}")

        data = res.get("data") or {}
        actor = data.get("actor") or {}
        account = actor.get("account") or {}
        alerts = account.get("alerts") or {}
        nrql_search = alerts.get("nrqlConditionsSearch") or {}
        conditions = nrql_search.get("nrqlConditions") or []

        for c in conditions:
            if isinstance(c, dict) and "name" in c:
                condition_names.add(c["name"])

        cursor = nrql_search.get("nextCursor")
        if not cursor:
            break

    return condition_names


def provision_alerts(
    account_id: int,
    api_key: str | None = None,
    policy_name: str = "RealEstate Crawler Operations",
    region: str = "us",
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> bool:
    """Create alert policy and NRQL conditions in New Relic with deduplication and fast-fail."""
    key = api_key or os.getenv("NEW_RELIC_API_KEY")
    if not key:
        logger.warning("NEW_RELIC_API_KEY is not set. Skipping alerts provisioning.")
        return False

    endpoint = get_nerdgraph_endpoint(region)

    try:
        policy_id = find_existing_policy_id(account_id, policy_name, key, endpoint=endpoint, timeout=timeout)
        if policy_id:
            logger.info(f"Reusing existing alert policy '{policy_name}' (ID: {policy_id})")
        else:
            policy_payload = build_alert_policy_payload(account_id, policy_name)
            policy_res = run_nerdgraph_query(policy_payload, key, endpoint=endpoint, timeout=timeout)
            if policy_res.get("errors"):
                logger.error(f"Failed to create alert policy: {policy_res['errors']}")
                return False

            created_policy = (policy_res.get("data") or {}).get("alertsPolicyCreate") or {}
            policy_id_raw = created_policy.get("id")
            if not policy_id_raw:
                logger.error("Could not obtain policy ID from response")
                return False

            policy_id = int(policy_id_raw)
            logger.info(f"Alert policy '{policy_name}' created (ID: {policy_id})")

        mutation_nrql = """
        mutation CreateNrqlCondition($accountId: Int!, $policyId: ID!, $condition: AlertsNrqlConditionStaticInput!) {
          alertsNrqlConditionStaticCreate(accountId: $accountId, policyId: $policyId, condition: $condition) {
            id
            name
          }
        }
        """

        existing_condition_names = find_existing_condition_names(account_id, policy_id, key, endpoint=endpoint, timeout=timeout)
        conditions = build_nrql_conditions(account_id, policy_id)
        failed_conditions = 0

        for cond in conditions:
            cond_name = cond["name"]
            if cond_name in existing_condition_names:
                logger.info(f"Condition '{cond_name}' already exists in policy. Skipping creation.")
                continue

            cond_input = {
                "name": cond_name,
                "enabled": cond["enabled"],
                "nrql": cond["nrql"],
                "terms": cond["terms"],
                "valueFunction": cond["valueFunction"],
            }
            cond_payload = {
                "query": mutation_nrql,
                "variables": {
                    "accountId": account_id,
                    "policyId": str(policy_id),
                    "condition": cond_input,
                },
            }
            c_res = run_nerdgraph_query(cond_payload, key, endpoint=endpoint, timeout=timeout)
            created_cond = (c_res.get("data") or {}).get("alertsNrqlConditionStaticCreate") or {}
            if c_res.get("errors") or not created_cond.get("id"):
                logger.warning(f"Error creating condition {cond_name}: {c_res.get('errors') or 'missing id in response'}")
                failed_conditions += 1
            else:
                logger.info(f"Successfully configured condition: {cond_name}")

        if failed_conditions > 0:
            logger.error(f"{failed_conditions} conditions failed to be configured.")
            return False

        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Exception during alert provisioning (Fast-Fail): {e}")
        return False


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Provision New Relic Alert Policies for RealEstate Crawler")
    parser.add_argument("--account-id", type=int, default=os.getenv("NEW_RELIC_ACCOUNT_ID"), help="New Relic Account ID")
    parser.add_argument("--api-key", default=os.getenv("NEW_RELIC_API_KEY"), help="New Relic User/API Key")
    parser.add_argument("--policy-name", default="RealEstate Crawler Operations", help="Alert Policy Name")
    parser.add_argument("--region", default=os.getenv("NEW_RELIC_REGION", "us"), choices=["us", "eu"], help="New Relic Region (us or eu)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SEC, help="Request timeout in seconds")

    args = parser.parse_args()
    if not args.account_id:
        logger.error("New Relic Account ID is required (via --account-id or NEW_RELIC_ACCOUNT_ID).")
        return 1

    if args.timeout <= 0:
        parser.error("--timeout must be > 0")

    timeout = min(args.timeout, 10.0)
    success = provision_alerts(
        account_id=args.account_id,
        api_key=args.api_key,
        policy_name=args.policy_name,
        region=args.region,
        timeout=timeout,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
