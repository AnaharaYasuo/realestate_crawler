# -*- coding: utf-8 -*-
import os

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "terraform")
WORKFLOW_FILE = os.path.join(PROJECT_ROOT, ".github", "workflows", "deploy-production.yml")


def test_artifact_registry_cleanup_policy_defined():
    """terraform/artifact_registry.tf に最新3世代保持およびUNTAGGED削除のクリーンアップポリシーが定義されていることを検証"""
    tf_file = os.path.join(TERRAFORM_DIR, "artifact_registry.tf")
    assert os.path.exists(tf_file), f"{tf_file} must exist"

    with open(tf_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_artifact_registry_repository" "crawler_repo"' in content
    assert "cleanup_policy_dry_run = false" in content
    assert "cleanup_policies" in content
    assert "keep_count = 3" in content
    assert 'action = "KEEP"' in content
    assert 'action = "DELETE"' in content
    assert 'tag_state = "UNTAGGED"' in content


def test_deploy_production_prune_step_defined():
    """deploy-production.yml に最新3世代超過イメージを自動削除するプルーニングステップが定義されていることを検証"""
    assert os.path.exists(WORKFLOW_FILE), f"{WORKFLOW_FILE} must exist"

    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Prune old images" in content or "prune" in content.lower()
    assert "gcloud artifacts docker images list" in content
    assert "1,3d" in content or "keep" in content.lower()
    assert "gcloud artifacts docker images delete" in content
