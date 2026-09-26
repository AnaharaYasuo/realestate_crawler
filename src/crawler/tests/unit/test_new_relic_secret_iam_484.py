# -*- coding: utf-8 -*-
"""Issue #484: crawler-runner SA must have Secret Accessor on New Relic license key."""
import os
import re


TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)


def test_iam_secret_accessor_includes_new_relic_license_key():
    """terraform/iam.tf secret_accessor for_each must include new_relic_license_key."""
    iam_path = os.path.join(TERRAFORM_DIR, "iam.tf")
    assert os.path.exists(iam_path), f"File not found: {iam_path}"

    with open(iam_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r'resource\s+"google_secret_manager_secret_iam_member"\s+"secret_accessor"\s+\{([\s\S]*?)\n\}',
        content,
    )
    assert match is not None, "secret_accessor resource not found in iam.tf"
    block = match.group(1)

    assert "new_relic_license_key" in block, (
        "secret_accessor for_each must include new_relic_license_key "
        "(Cloud Run SecretsAccessCheckFailed otherwise)"
    )
    assert (
        "google_secret_manager_secret.new_relic_license_key.secret_id" in block
    ), "new_relic_license_key must reference google_secret_manager_secret.new_relic_license_key.secret_id"
    assert "roles/secretmanager.secretAccessor" in block
    assert "google_service_account.crawler_runner.email" in block
