#!/usr/bin/env python3
"""
New Relic Comprehensive Unified Dashboard Provisioner for Real Estate Crawler.
Deletes legacy dashboards and provisions a complete full-stack observability dashboard
covering Crawling, HTTP Traffic, Database, Parsers, Containers, LLM GenAI, ML, and Errors.
"""
import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

NERDGRAPH_ENDPOINT = "https://api.newrelic.com/graphql"
DEFAULT_TIMEOUT_SEC = 10.0
DEFAULT_DASHBOARD_NAME = "RealEstate Full-Stack Unified Observability"


MANAGED_DASHBOARD_NAMES = frozenset({
    DEFAULT_DASHBOARD_NAME,
    "GCP Real Estate System & Monitoring Overview",
})


def build_dashboard_delete_payload(guid: str) -> dict[str, Any]:
    """Build NerdGraph mutation to delete an existing dashboard by GUID."""
    mutation = """
    mutation DeleteDashboard($guid: EntityGuid!) {
      dashboardDelete(guid: $guid) {
        errors {
          description
          type
        }
        status
      }
    }
    """
    return {"query": mutation, "variables": {"guid": guid}}


def build_dashboard_create_payload(
    account_id: int,
    dashboard_name: str = DEFAULT_DASHBOARD_NAME,
) -> dict[str, Any]:
    """Build NerdGraph mutation to create a complete full-stack dashboard."""
    mutation = """
    mutation CreateDashboard($accountId: Int!, $dashboard: DashboardInput!) {
      dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
        errors {
          description
          type
        }
        entityResult {
          guid
          name
        }
      }
    }
    """
    widgets = [
        # Row 1: High-Level Overview
        {
            "title": "Total Scraped Items (7 Days)",
            "layout": {"column": 1, "row": 1, "width": 4, "height": 3},
            "configuration": {
                "billboard": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT sum(`count`) AS 'Scraped Items' FROM CrawlerExecution SINCE 7 days ago",
                        }
                    ]
                }
            },
        },
        {
            "title": "Crawler Zero-Count Failures (7 Days)",
            "layout": {"column": 5, "row": 1, "width": 4, "height": 3},
            "configuration": {
                "billboard": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT count(*) AS 'Zero-Count Failures' FROM CrawlerExecution WHERE zero_count = true OR (`count` = 0 AND status != 'no_updates') SINCE 7 days ago",
                        }
                    ]
                }
            },
        },
        {
            "title": "Avg Scraping Throughput (Items/sec)",
            "layout": {"column": 9, "row": 1, "width": 4, "height": 3},
            "configuration": {
                "billboard": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(items_per_sec) AS 'Avg Items/Sec' FROM CrawlerExecution WHERE items_per_sec > 0 SINCE 7 days ago",
                        }
                    ]
                }
            },
        },
        # Row 2: Crawling & Portal Performance
        {
            "title": "Scraped Items by Site & Property Type",
            "layout": {"column": 1, "row": 4, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT sum(`count`) FROM CrawlerExecution FACET site_name, property_type SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        {
            "title": "Scraping Duration by Site (Seconds)",
            "layout": {"column": 7, "row": 4, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(duration_sec) FROM CrawlerExecution FACET site_name SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 3: Network & HTTP Scraping Status
        {
            "title": "Target Portal HTTP Response Codes (403/429/500 Alerting)",
            "layout": {"column": 1, "row": 7, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT count(*) FROM HttpRequestEvent FACET status_code, site_name SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        {
            "title": "HTTP Request Latency by Portal Domain (ms)",
            "layout": {"column": 7, "row": 7, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(duration_ms) FROM HttpRequestEvent FACET domain SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 4: Database & ProxySQL Telemetry
        {
            "title": "Database Bulk Upsert Duration (ms)",
            "layout": {"column": 1, "row": 10, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(duration_ms), max(duration_ms) FROM DatabaseEvent FACET table_name SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        {
            "title": "Database Saved Records Count",
            "layout": {"column": 7, "row": 10, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT sum(row_count) FROM DatabaseEvent FACET table_name SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 5: Parser Fine-Grained Performance
        {
            "title": "DOM Pure Parser Execution Time (ms/property)",
            "layout": {"column": 1, "row": 13, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(duration_ms) FROM ParserEvent FACET site_name, property_type SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        {
            "title": "Parser Missing Fields Ratio (%)",
            "layout": {"column": 7, "row": 13, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(missing_ratio) FROM ParserEvent FACET site_name SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 6: Container Resources (Cloud Run cgroup)
        {
            "title": "Container Memory Usage % (Alert Threshold: 85%)",
            "layout": {"column": 1, "row": 16, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(memoryPercent), max(memoryPercent) FROM ContainerSample FACET containerName SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        {
            "title": "Container Memory Usage (MB) & Limit",
            "layout": {"column": 7, "row": 16, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT average(memoryUsageMb), average(memoryLimitMb) FROM ContainerSample FACET containerName SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 7: GenAI / LLM & ML Inference
        {
            "title": "Gemini LLM Token Consumption & Est. Cost (USD)",
            "layout": {"column": 1, "row": 19, "width": 6, "height": 3},
            "configuration": {
                "table": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT sum(total_tokens) AS 'Total Tokens', sum(cost_usd) AS 'Est USD' FROM LlmEvent FACET model SINCE 7 days ago",
                        }
                    ]
                }
            },
        },
        {
            "title": "ML Price Estimation & Bargain Property Counts",
            "layout": {"column": 7, "row": 19, "width": 6, "height": 3},
            "configuration": {
                "line": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT sum(evaluated_count) AS 'Evaluated', sum(bargain_count) AS 'Bargain Found' FROM MlInferenceEvent FACET model_type SINCE 7 days ago TIMESERIES",
                        }
                    ]
                }
            },
        },
        # Row 8: Logs & Errors
        {
            "title": "Recent Application Error Logs",
            "layout": {"column": 1, "row": 22, "width": 12, "height": 4},
            "configuration": {
                "table": {
                    "nrqlQueries": [
                        {
                            "accountId": account_id,
                            "query": "SELECT timestamp, message, hostname, `entity.name` FROM Log WHERE level IN ('ERROR', 'CRITICAL') SINCE 3 days ago LIMIT 50",
                        }
                    ]
                }
            },
        },
    ]

    return {
        "query": mutation,
        "variables": {
            "accountId": account_id,
            "dashboard": {
                "name": dashboard_name,
                "permissions": "PUBLIC_READ_WRITE",
                "pages": [
                    {
                        "name": "Unified Real Estate Operations",
                        "widgets": widgets,
                    }
                ],
            },
        },
    }


def run_nerdgraph_query(
    payload: dict[str, Any],
    api_key: str,
    endpoint: str = NERDGRAPH_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Execute NerdGraph query with finite timeout."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "API-Key": api_key,
            "User-Agent": "RealEstate-DashboardSetup/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_existing_dashboards(api_key: str, account_id: int | None = None, timeout: float = DEFAULT_TIMEOUT_SEC) -> list[dict[str, Any]]:
    """Find all existing dashboards in the account."""
    query = """
    query SearchDashboards {
      actor {
        entitySearch(query: "type = 'DASHBOARD'") {
          results {
            entities {
              guid
              name
              tags {
                key
                values
              }
            }
          }
        }
      }
    }
    """
    res = run_nerdgraph_query({"query": query}, api_key, timeout=timeout)
    if res.get("errors"):
        raise RuntimeError(f"Failed to search dashboards: {res['errors']}")
    entities = res.get("data", {}).get("actor", {}).get("entitySearch", {}).get("results", {}).get("entities", [])
    parent_dashboards = []
    for ent in entities:
        is_page = any(t.get("key") == "isDashboardPage" and "true" in t.get("values", []) for t in ent.get("tags", []))
        if is_page:
            continue
        if account_id is not None:
            acc_tags = [v for t in ent.get("tags", []) if t.get("key") == "accountId" for v in t.get("values", [])]
            if acc_tags and str(account_id) not in acc_tags:
                continue
        parent_dashboards.append(ent)
    return parent_dashboards


def delete_dashboard(guid: str, api_key: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> bool:
    """Delete a dashboard by GUID."""
    payload = build_dashboard_delete_payload(guid)
    res = run_nerdgraph_query(payload, api_key, timeout=timeout)
    data = res.get("data", {}).get("dashboardDelete", {})
    if data.get("status") == "SUCCESS":
        return True
    logger.warning(f"Dashboard delete returned: {res}")
    return False


def create_unified_dashboard(account_id: int, api_key: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> str:
    """Create the unified dashboard and return its GUID."""
    payload = build_dashboard_create_payload(account_id)
    res = run_nerdgraph_query(payload, api_key, timeout=timeout)
    if res.get("errors"):
        raise RuntimeError(f"Dashboard creation failed: {res['errors']}")
    data = res.get("data", {}).get("dashboardCreate", {})
    if data.get("errors"):
        raise RuntimeError(f"Dashboard creation errors: {data['errors']}")
    entity = data.get("entityResult") or {}
    return entity.get("guid", "")


def main() -> None:
    env_account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
    default_acc_id = int(env_account_id) if env_account_id and env_account_id.isdigit() else None

    parser = argparse.ArgumentParser(description="Provision New Relic Unified Dashboard")
    parser.add_argument("--account-id", type=int, default=default_acc_id, help="New Relic Account ID")
    parser.add_argument("--api-key", default=os.getenv("NEW_RELIC_API_KEY"), help="New Relic User API Key")
    parser.add_argument("--replace-all", action="store_true", help="Delete all existing dashboards before creating")
    args = parser.parse_args()

    account_id = args.account_id
    if account_id is None:
        logger.error("NEW_RELIC_ACCOUNT_ID environment variable or --account-id argument is required")
        sys.exit(1)

    api_key = args.api_key or os.getenv("NEW_RELIC_API_KEY")
    if not api_key:
        logger.error("NEW_RELIC_API_KEY is required")
        sys.exit(1)

    dashboards = find_existing_dashboards(api_key, account_id=account_id)
    logger.info(f"Found {len(dashboards)} existing dashboard(s)")

    if args.replace_all:
        for d in dashboards:
            guid = d["guid"]
            name = d.get("name") or ""
            if name in MANAGED_DASHBOARD_NAMES:
                logger.info(f"Deleting dashboard: {name} ({guid})")
                success = delete_dashboard(guid, api_key)
                if not success:
                    logger.error(f"Failed to delete dashboard {guid}, aborting.")
                    sys.exit(1)

    logger.info("Creating comprehensive unified dashboard...")
    new_guid = create_unified_dashboard(account_id, api_key)
    logger.info(f"Unified dashboard successfully created! GUID: {new_guid}")




if __name__ == "__main__":
    main()
