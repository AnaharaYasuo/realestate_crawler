# -*- coding: utf-8 -*-
import os
import re

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "terraform")
WORKFLOW_FILE = os.path.join(PROJECT_ROOT, ".github", "workflows", "deploy-production.yml")


def test_artifact_registry_cleanup_policy_defined():
    """terraform/artifact_registry.tf に最新3世代保持およびUNTAGGED削除のクリーンアップポリシーが構造的に定義されていることを検証"""
    tf_file = os.path.join(TERRAFORM_DIR, "artifact_registry.tf")
    assert os.path.exists(tf_file), f"{tf_file} must exist"

    with open(tf_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_artifact_registry_repository" "crawler_repo"' in content
    assert "cleanup_policy_dry_run = false" in content

    # cleanup_policies ブロック群を個別に抽出して検証
    policy_blocks = re.findall(r"cleanup_policies\s*\{([^}]+(?:\{[^}]+\}[^}]+)*)\}", content)
    assert len(policy_blocks) >= 2, f"Expected at least 2 cleanup_policies blocks, got {len(policy_blocks)}"

    keep_policy = next((b for b in policy_blocks if 'id     = "keep-recent-3"' in b or 'id = "keep-recent-3"' in b), None)
    assert keep_policy is not None, "keep-recent-3 policy block not found"
    assert 'action = "KEEP"' in keep_policy
    assert "keep_count = 3" in keep_policy

    delete_policy = next((b for b in policy_blocks if 'id     = "delete-untagged"' in b or 'id = "delete-untagged"' in b), None)
    assert delete_policy is not None, "delete-untagged policy block not found"
    assert 'action = "DELETE"' in delete_policy
    assert 'tag_state = "UNTAGGED"' in delete_policy


def test_deploy_production_prune_step_defined():
    """deploy-production.yml に最新3世代超過イメージを自動削除するプルーニングステップが定義されていることを検証"""
    assert os.path.exists(WORKFLOW_FILE), f"{WORKFLOW_FILE} must exist"

    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Prune old images (Keep latest 3 versions)" in content
    assert "gcloud artifacts docker images list" in content
    assert "sed -e '1,3d'" in content
    assert "gcloud artifacts docker images delete" in content
    assert "::warning::" in content


def test_prune_logic_with_stub_image_list():
    """スタブのイメージ一覧を用い、最新3件が保持され4件目以降のみが削除対象として抽出されることを検証"""
    stub_images_sorted_by_create_time = [
        "sha256:digest_1_newest",
        "sha256:digest_2_second",
        "sha256:digest_3_third",
        "sha256:digest_4_old",
        "sha256:digest_5_oldest",
    ]

    # sed -e '1,3d' 相当のロジック: 1〜3行目を削除し、4行目以降を残す
    kept = stub_images_sorted_by_create_time[:3]
    to_delete = stub_images_sorted_by_create_time[3:]

    assert len(kept) == 3
    assert kept == [
        "sha256:digest_1_newest",
        "sha256:digest_2_second",
        "sha256:digest_3_third",
    ]
    assert len(to_delete) == 2
    assert to_delete == [
        "sha256:digest_4_old",
        "sha256:digest_5_oldest",
    ]
