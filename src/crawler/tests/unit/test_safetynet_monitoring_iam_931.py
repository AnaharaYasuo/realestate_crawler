"""Issue #931: safety-net は Cloud Monitoring で通信量を取得するため crawler_runner に monitoring.viewer が必要。"""
import os
import re

IAM_TF = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../terraform/iam.tf")
)


def test_crawler_runner_has_monitoring_viewer():
    with open(IAM_TF, encoding="utf-8") as f:
        content = f.read()
    assert re.search(
        r'role\s*=\s*"roles/monitoring\.viewer"[^}]*google_service_account\.crawler_runner\.email',
        content,
    )
