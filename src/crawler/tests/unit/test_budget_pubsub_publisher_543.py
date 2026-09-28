# -*- coding: utf-8 -*-
"""Issue #543: Monitoring notification agent must be able to publish to budget_alert_topic."""
import os
import re

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)
MONITORING_AGENT = (
    "serviceAccount:service-${data.google_project.current.number}"
    "@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
)


def _strip_hcl_line_comments(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _read_all_tf() -> str:
    contents = []
    for name in sorted(os.listdir(TERRAFORM_DIR)):
        if name.endswith(".tf"):
            with open(os.path.join(TERRAFORM_DIR, name), "r", encoding="utf-8") as f:
                contents.append(_strip_hcl_line_comments(f.read()))
    return "\n".join(contents)


def _resource_block(content: str, rtype: str, name: str) -> str:
    match = re.search(
        rf'resource\s+"{rtype}"\s+"{name}"\s+\{{([\s\S]*?)\n\}}', content
    )
    assert match is not None, f"{rtype}.{name} not found"
    return match.group(1)


def test_monitoring_agent_has_topic_scoped_publisher():
    block = _resource_block(
        _read_all_tf(), "google_pubsub_topic_iam_member", "monitoring_notification_publisher"
    )
    assert re.search(r"topic\s*=\s*google_pubsub_topic\.budget_alert_topic\.name", block)
    assert re.search(r'role\s*=\s*"roles/pubsub\.publisher"', block)
    assert re.search(r"member\s*=\s*\"" + re.escape(MONITORING_AGENT) + '"', block)


def test_monitoring_agent_email_derived_from_project_number():
    content = _read_all_tf()
    data_match = re.search(r'data\s+"google_project"\s+"current"\s+\{([\s\S]*?)\n\}', content)
    assert data_match is not None, 'data "google_project" "current" not found'
    assert re.search(r"project_id\s*=\s*var\.project_id", data_match.group(1))
    assert "634731722260" not in content


def test_monitoring_agent_not_granted_project_wide_publisher():
    content = _read_all_tf()
    for match in re.finditer(
        r'resource\s+"google_project_iam_member"\s+"\w+"\s+\{([\s\S]*?)\n\}', content
    ):
        block = match.group(1)
        assert not (
            "roles/pubsub.publisher" in block and "gcp-sa-monitoring-notification" in block
        ), "Monitoring agent must not receive project-level pubsub.publisher"


def test_deploy_sa_can_manage_budget_topic_iam():
    block = _resource_block(
        _read_all_tf(), "google_pubsub_topic_iam_member", "github_actions_budget_topic_iam"
    )
    assert re.search(r"topic\s*=\s*google_pubsub_topic\.budget_alert_topic\.name", block)
    assert 'role    = "projects/${var.project_id}/roles/pubsubTopicIamManager"' in block
    assert "roles/pubsub.admin" not in block
    assert 'member  = "serviceAccount:${var.github_actions_sa_email}"' in block


def test_notification_channel_depends_on_publisher_grant():
    block = _resource_block(
        _read_all_tf(), "google_monitoring_notification_channel", "alert_pubsub"
    )
    depends = re.search(r"depends_on\s*=\s*\[([\s\S]*?)\]", block)
    assert depends is not None
    assert "google_pubsub_topic_iam_member.monitoring_notification_publisher" in depends.group(1)


def test_publisher_grant_depends_on_deploy_sa_topic_iam():
    block = _resource_block(
        _read_all_tf(), "google_pubsub_topic_iam_member", "monitoring_notification_publisher"
    )
    depends = re.search(r"depends_on\s*=\s*\[([\s\S]*?)\]", block)
    assert depends is not None
    assert "google_pubsub_topic_iam_member.github_actions_budget_topic_iam" in depends.group(1)
