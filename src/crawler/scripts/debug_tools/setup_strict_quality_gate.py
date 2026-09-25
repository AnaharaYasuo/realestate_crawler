"""
SonarCloud Strict Quality Gate Provisioning Tool (setup_strict_quality_gate.py)
Issue #436: Automates configuration and selection of a strict Quality Gate
that fails on any new issues (new_violations > 0) without false failures from coverage exclusion.
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

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

try:
    import setup_env
    setup_env.init_environment()
except ImportError:
    pass

logger = logging.getLogger(__name__)

SONARCLOUD_API_BASE: str = "https://sonarcloud.io/api"
DEFAULT_ORG: str = "anaharayasuo"
DEFAULT_PROJECT: str = "AnaharaYasuo_realestate_crawler"
DEFAULT_GATE_NAME: str = "Strict Gate"

DEFAULT_CONDITIONS: list[dict[str, str]] = [
    {"metric": "new_violations", "op": "GT", "error": "0"},
    {"metric": "new_reliability_rating", "op": "GT", "error": "1"},
    {"metric": "new_security_rating", "op": "GT", "error": "1"},
    {"metric": "new_maintainability_rating", "op": "GT", "error": "1"},
    {"metric": "new_duplicated_lines_density", "op": "GT", "error": "3"},
    {"metric": "new_security_hotspots_reviewed", "op": "LT", "error": "100"},
]

UNWANTED_METRICS = {"new_coverage", "branch_coverage", "coverage"}


def api_request(
    endpoint: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    token: str = "",
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Execute authenticated SonarCloud API request."""
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{SONARCLOUD_API_BASE}/{endpoint}{query}"
    
    encoded_data = None
    if data is not None:
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=encoded_data, method=method)
    if token:
        import base64
        auth_header = base64.b64encode(f"{token}:".encode()).decode("ascii")
        req.add_header("Authorization", f"Basic {auth_header}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            if not content.strip():
                return {}
            return json.loads(content)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error(f"SonarCloud API HTTP {exc.code} for {url}: {err_body}")
        raise RuntimeError(f"SonarCloud API HTTP {exc.code}: {err_body}") from exc


def ensure_strict_quality_gate(
    token: str,
    org: str = DEFAULT_ORG,
    project: str = DEFAULT_PROJECT,
    gate_name: str = DEFAULT_GATE_NAME,
    dry_run: bool = False,
) -> int:
    """Ensure Strict Quality Gate exists, configured, and selected for project."""
    gates_resp = api_request("qualitygates/list", params={"organization": org}, token=token)
    gates = gates_resp.get("qualitygates", [])

    target_gate = next((g for g in gates if g.get("name") == gate_name), None)
    gate_id: int

    if not target_gate:
        if dry_run:
            print(f"[DRY-RUN] Would create quality gate '{gate_name}' in org '{org}'")
            return -1
        print(f"Creating quality gate '{gate_name}' in org '{org}'...")
        create_resp = api_request(
            "qualitygates/create",
            method="POST",
            data={"name": gate_name, "organization": org},
            token=token,
        )
        gate_id = int(create_resp.get("id"))
        existing_conditions = []
    else:
        gate_id = int(target_gate.get("id"))
        gate_resp = api_request(
            "qualitygates/show",
            params={"name": gate_name, "organization": org},
            token=token,
        )
        existing_conditions = gate_resp.get("conditions", [])
        print(f"Found existing quality gate '{gate_name}' (ID: {gate_id})")

    # Clean up unwanted metrics (e.g. coverage metrics causing false failures)
    for cond in existing_conditions:
        metric = cond.get("metric")
        cond_id = cond.get("id")
        if metric in UNWANTED_METRICS and cond_id:
            if dry_run:
                print(f"[DRY-RUN] Would delete condition ID {cond_id} (metric: {metric})")
            else:
                print(f"Deleting unwanted condition ID {cond_id} (metric: {metric})...")
                api_request(
                    "qualitygates/delete_condition",
                    method="POST",
                    data={"id": cond_id, "organization": org},
                    token=token,
                )

    # Ensure required conditions
    existing_metrics = {c.get("metric") for c in existing_conditions if c.get("metric") not in UNWANTED_METRICS}
    for req_cond in DEFAULT_CONDITIONS:
        metric = req_cond["metric"]
        if metric not in existing_metrics:
            if dry_run:
                print(f"[DRY-RUN] Would add condition: {req_cond}")
            else:
                print(f"Adding condition: {req_cond}...")
                api_request(
                    "qualitygates/create_condition",
                    method="POST",
                    data={
                        "gateId": gate_id,
                        "metric": req_cond["metric"],
                        "op": req_cond["op"],
                        "error": req_cond["error"],
                        "organization": org,
                    },
                    token=token,
                )

    # Select gate for project
    if dry_run:
        print(f"[DRY-RUN] Would select gate ID {gate_id} for project '{project}'")
    else:
        print(f"Associating project '{project}' with quality gate ID {gate_id}...")
        api_request(
            "qualitygates/select",
            method="POST",
            data={"gateId": gate_id, "projectKey": project, "organization": org},
            token=token,
        )
        print(f"Successfully selected Quality Gate '{gate_name}' (ID: {gate_id}) for '{project}'")

    return gate_id


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Ensure SonarCloud Strict Quality Gate")
    parser.add_argument("--token", default=os.getenv("SONAR_TOKEN", ""), help="SonarCloud User Token")
    parser.add_argument("--org", default=DEFAULT_ORG, help="SonarCloud Organization")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="SonarCloud Project Key")
    parser.add_argument("--gate-name", default=DEFAULT_GATE_NAME, help="Quality Gate Name")
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without modifying")

    args = parser.parse_args(argv)
    if not args.token and not args.dry_run:
        logger.error("SONAR_TOKEN is required (via --token or environment variable)")
        print("[ERROR] SONAR_TOKEN is required", file=sys.stderr)
        return 1

    try:
        ensure_strict_quality_gate(
            token=args.token,
            org=args.org,
            project=args.project,
            gate_name=args.gate_name,
            dry_run=args.dry_run,
        )
        return 0
    except Exception as exc:
        logger.exception("Failed to setup strict quality gate")
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
