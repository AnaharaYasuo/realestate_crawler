# -*- coding: utf-8 -*-
"""Issue #484: crawler-runner SA must have Secret Accessor on New Relic license key."""
import os
import re


TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)


def _strip_hcl_line_comments(text: str) -> str:
    """Remove Terraform # line comments so commented-out entries cannot pass."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_iam_secret_accessor_includes_new_relic_license_key():
    """terraform/iam.tf secret_accessor for_each must map new_relic_license_key actively."""
    iam_path = os.path.join(TERRAFORM_DIR, "iam.tf")
    assert os.path.exists(iam_path), f"File not found: {iam_path}"

    with open(iam_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r'resource\s+"google_secret_manager_secret_iam_member"\s+"secret_accessor"\s+\{([\s\S]*?)\n\}',
        content,
    )
    assert match is not None, "secret_accessor resource not found in iam.tf"
    block = _strip_hcl_line_comments(match.group(1))

    for_each_match = re.search(r"for_each\s*=\s*\{([\s\S]*?)\}", block)
    assert for_each_match is not None, "secret_accessor for_each map not found"
    for_each_body = for_each_match.group(1)

    entry_match = re.search(
        r"new_relic_license_key\s*=\s*"
        r"google_secret_manager_secret\.new_relic_license_key\.secret_id",
        for_each_body,
    )
    assert entry_match is not None, (
        "secret_accessor for_each must contain active map entry "
        "new_relic_license_key = google_secret_manager_secret.new_relic_license_key.secret_id"
    )
    assert "roles/secretmanager.secretAccessor" in block
    assert "google_service_account.crawler_runner.email" in block
    assert re.search(r"secret_id\s*=\s*each\.value", block)
