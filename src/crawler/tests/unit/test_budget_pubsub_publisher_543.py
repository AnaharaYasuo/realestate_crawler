# -*- coding: utf-8 -*-
"""Issue #543: Monitoring notification agent must be able to publish to budget_alert_topic."""
import os
import re

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)
MONITORING_AGENT = (
    "serviceAccount:${google_project_service_identity.monitoring_notification_agent.email}"
)
PROJECT_LEVEL_IAM_TYPES = ("google_project_iam_member", "google_project_iam_binding")


def _strip_hcl_comments(text: str) -> str:
    """Remove #, // line comments and /* */ block comments so commented-out grants cannot pass."""
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith(("#", "//"))
    )


def _read_all_tf() -> str:
    contents = []
    for name in sorted(os.listdir(TERRAFORM_DIR)):
        if name.endswith(".tf"):
            with open(os.path.join(TERRAFORM_DIR, name), "r", encoding="utf-8") as f:
                contents.append(_strip_hcl_comments(f.read()))
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


def test_monitoring_agent_identity_is_terraform_managed():
    content = _read_all_tf()
    block = _resource_block(
        content, "google_project_service_identity", "monitoring_notification_agent"
    )
    assert re.search(r"provider\s*=\s*google-beta", block)
    assert re.search(r"project\s*=\s*var\.project_id", block)
    assert re.search(r'service\s*=\s*"monitoring\.googleapis\.com"', block)
    assert "634731722260" not in content
    assert "gcp-sa-monitoring-notification" not in content


def test_monitoring_agent_not_granted_project_wide_publisher():
    content = _read_all_tf()
    for rtype in PROJECT_LEVEL_IAM_TYPES:
        for match in re.finditer(
            rf'resource\s+"{rtype}"\s+"\w+"\s+\{{([\s\S]*?)\n\}}', content
        ):
            block = match.group(1)
            assert not (
                "roles/pubsub.publisher" in block
                and "monitoring_notification_agent" in block
            ), f"Monitoring agent must not receive project-level pubsub.publisher via {rtype}"


def test_strip_hcl_comments_ignores_all_comment_styles():
    commented = (
        '# role = "roles/pubsub.publisher"\n'
        '// role = "roles/pubsub.publisher"\n'
        '/* role = "roles/pubsub.publisher" */\n'
        '/*\n  role = "roles/pubsub.publisher"\n*/\n'
        'role = "roles/viewer"\n'
    )
    stripped = _strip_hcl_comments(commented)
    assert "roles/pubsub.publisher" not in stripped
    assert 'role = "roles/viewer"' in stripped


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
