# -*- coding: utf-8 -*-
"""
Issue #814: クローラーパイプライン過剰プロビジョニング適正化の回帰テスト
- realestate-crawler-pipeline-prod のスペック (1 vCPU / 3 GiB)
- terraform/variables.tf の crawler_cpu ("1") および crawler_memory ("3Gi")
- terraform/cloud_run_job.tf の crawler_pipeline_job 参照
- .github/workflows/deploy-production.yml のリソース設定同期
"""
import os
import re

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)
DEPLOY_WORKFLOW_PATH = os.path.join(
    TERRAFORM_DIR, "..", ".github", "workflows", "deploy-production.yml"
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _strip_comments(content: str) -> str:
    return "\n".join(
        re.sub(r"\s#.*$", "", line)
        for line in content.splitlines()
        if not line.lstrip().startswith("#")
    )


def _variable_default(name: str) -> str:
    content = _strip_comments(_read(os.path.join(TERRAFORM_DIR, "variables.tf")))
    head = f'variable "{name}"'
    assert head in content, f'variable "{name}" not found in variables.tf'
    block = content.split(head, 1)[1].split("\nvariable ", 1)[0]
    match = re.search(r'default\s*=\s*"([^"]+)"', block)
    assert match, f'default value not found for variable "{name}"'
    return match.group(1)


def _job_block(name: str) -> str:
    content = _strip_comments(_read(os.path.join(TERRAFORM_DIR, "cloud_run_job.tf")))
    head = f'resource "google_cloud_run_v2_job" "{name}"'
    assert head in content, f'job "{name}" not found in cloud_run_job.tf'
    return content.split(head, 1)[1].split("\nresource ", 1)[0]


class TestCrawlerResourceOptimization814:
    """Issue #814: クローラーパイプラインのリソース適正化検証"""

    def test_crawler_cpu_variable_is_one(self):
        assert _variable_default("crawler_cpu") == "1"

    def test_crawler_memory_variable_is_three_gib(self):
        assert _variable_default("crawler_memory") == "3Gi"

    def test_crawler_pipeline_job_uses_variables(self):
        block = _job_block("crawler_pipeline_job")
        assert "cpu    = var.crawler_cpu" in block
        assert "memory = var.crawler_memory" in block

    def test_deploy_production_syncs_crawler_cpu_and_memory(self):
        content = _strip_comments(_read(DEPLOY_WORKFLOW_PATH))
        head = "gcloud run jobs update realestate-crawler-pipeline-prod"
        assert head in content
        section = content.split(head, 1)[1].split("gcloud run ", 1)[0]
        assert "--cpu=1" in section
        assert "--memory=3Gi" in section
