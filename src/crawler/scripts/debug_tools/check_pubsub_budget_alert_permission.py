"""Check GCP Pub/Sub budget alert notification permissions and diagnostic parsing."""

import json
import os
import sys
from typing import Any, Dict, Tuple


def parse_pubsub_permission_incident(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Parse GCP Cloud Monitoring incident payload and determine if it's Pub/Sub PERMISSION_DENIED.

    Args:
        payload: Incident payload or log entry dict.

    Returns:
        Tuple of (is_pubsub_permission_denied, remediation_summary)
    """
    summary = payload.get("summary", "")
    if not summary and "incident" in payload:
        summary = payload["incident"].get("summary", "")

    if "PERMISSION_DENIED" in summary and "Cloud Pub/Sub" in summary:
        topic_name = "unknown"
        if "topics/" in summary:
            parts = summary.split("topics/")
            if len(parts) > 1:
                raw_topic = parts[1].split()[0]
                topic_name = raw_topic.rstrip(".:,;")

        remediation = (
            f"Pub/Sub Permission Denied for topic '{topic_name}'. "
            "Ensure 'roles/pubsub.publisher' is assigned to "
            "service-PROJECT_NUMBER@gcp-sa-monitoring-notification.iam.gserviceaccount.com "
            "and Cloud Pub/Sub API is enabled."
        )
        return True, remediation

    return False, "No Pub/Sub permission issue detected."


def main() -> None:
    """CLI Entry point for testing payload diagnosis."""
    sample_payload = {
        "incident_id": "0.od2x7rymkzr4",
        "errorReference": "ixWACIOAgMzSg6rALBCEgIDM0oOqwCwYDDIKGICAgMzSg6rALGiDgIDM0oOqwCwD",
        "summary": (
            "An error occurred while publishing notification to Cloud Pub/Sub "
            "topic projects/sumifu/topics/budget-alert-topic-prod. Possible causes: "
            "1) you don't have the required role; or 2) Cloud Pub/Sub API is not "
            "enabled in your project: PERMISSION_DENIED"
        ),
    }

    is_denied, remediation = parse_pubsub_permission_incident(sample_payload)
    print(f"Incident Detected: {is_denied}")
    print(f"Remediation Plan: {remediation}")


if __name__ == "__main__":
    main()
