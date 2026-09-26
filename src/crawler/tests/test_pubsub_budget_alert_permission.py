import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.crawler.scripts.debug_tools.check_pubsub_budget_alert_permission import (
    parse_pubsub_permission_incident,
)


def test_parse_pubsub_permission_incident_positive() -> None:
    """Test correctly identifying Pub/Sub PERMISSION_DENIED incident."""
    payload = {
        "incident_id": "0.od2x7rymkzr4",
        "errorReference": "ixWACIOAgMzSg6rALBCEgIDM0oOqwCwYDDIKGICAgMzSg6rALGiDgIDM0oOqwCwD",
        "summary": (
            "An error occurred while publishing notification to Cloud Pub/Sub topic "
            "projects/sumifu/topics/budget-alert-topic-prod. Possible causes: 1) you "
            "don't have the required role; or 2) Cloud Pub/Sub API is not enabled in "
            "your project: PERMISSION_DENIED"
        ),
    }

    is_denied, remediation = parse_pubsub_permission_incident(payload)
    assert is_denied is True
    assert "budget-alert-topic-prod" in remediation
    assert "roles/pubsub.publisher" in remediation


def test_parse_pubsub_permission_incident_negative() -> None:
    """Test non-PubSub or non-PERMISSION_DENIED payloads."""
    payload = {
        "incident_id": "1.abc123xyz",
        "summary": "Normal alert notification delivered successfully.",
    }

    is_denied, remediation = parse_pubsub_permission_incident(payload)
    assert is_denied is False
    assert remediation == "No Pub/Sub permission issue detected."
