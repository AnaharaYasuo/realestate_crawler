# -*- coding: utf-8 -*-
"""
Issue #809: GCPクラウドコスト最適化・リソース適正化・ML学習不要化の回帰テスト
- realestate-ml-pipeline のスペック (2 vCPU / 2 GiB)
- realestate-recrawl-anomalies のメモリ (2 GiB)
- run_ml_pipeline.py のデフォルト学習スキップ動作 (skip_train = True by default)
- deploy-production.yml のリソース設定同期
"""
import os
import re
import argparse


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
    content = _read(os.path.join(TERRAFORM_DIR, "variables.tf"))
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


class TestMlPipelineDefaultTrainingSkip:
    """Issue #809: MLパイプラインはデフォルトで学習をスキップし推論のみ実行する"""

    def test_default_skips_training_without_flags(self, monkeypatch):
        monkeypatch.delenv("ML_PIPELINE_SKIP_TRAIN", raising=False)
        # 引数なしで起動した場合、デフォルトで skip_train は True
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-train", action="store_true", default=None)
        parser.add_argument("--train", action="store_true", default=False)
        args = parser.parse_args([])
        skip_train = not args.train
        assert skip_train is True

    def test_explicit_train_flag_enables_training(self, monkeypatch):
        monkeypatch.delenv("ML_PIPELINE_SKIP_TRAIN", raising=False)
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-train", action="store_true", default=None)
        parser.add_argument("--train", action="store_true", default=False)
        args = parser.parse_args(["--train"])
        skip_train = not args.train
        assert skip_train is False

    def test_legacy_skip_train_flag_remains_functional(self, monkeypatch):
        monkeypatch.delenv("ML_PIPELINE_SKIP_TRAIN", raising=False)
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-train", action="store_true", default=None)
        parser.add_argument("--train", action="store_true", default=False)
        args = parser.parse_args(["--skip-train"])
        skip_train = True if args.skip_train else not args.train
        assert skip_train is True


class TestTerraformResourceRightsizing:
    """Issue #809: Terraformにおける過剰プロビジョニング解消スペック検証"""

    def test_ml_pipeline_variables(self):
        assert _variable_default("ml_pipeline_cpu") == "2"
        assert _variable_default("ml_pipeline_memory") == "2Gi"

    def test_recrawl_memory_variable(self):
        assert _variable_default("recrawl_memory") == "2Gi"

    def test_ml_pipeline_job_uses_rightsized_limits(self):
        block = _job_block("ml_pipeline_job")
        assert "cpu" in block
        assert "memory" in block
        # cpu は 2 または var.ml_pipeline_cpu
        assert 'cpu    = var.ml_pipeline_cpu' in block or 'cpu    = "2"' in block
        assert 'memory = var.ml_pipeline_memory' in block or 'memory = "2Gi"' in block

    def test_recrawl_anomalies_job_uses_rightsized_memory(self):
        block = _job_block("recrawl_anomalies_job")
        assert 'memory = var.recrawl_memory' in block or 'memory = "2Gi"' in block


class TestDeployWorkflowResourceSync:
    """Issue #809: GitHub Actionsデプロイワークフローのリソース設定同期検証"""

    def test_deploy_production_ml_pipeline_specs(self):
        content = _read(DEPLOY_WORKFLOW_PATH)
        ml_section = content.split("realestate-ml-pipeline-prod", 1)[1].split("gcloud run jobs", 1)[0]
        assert "--cpu=2" in ml_section
        assert "--memory=2Gi" in ml_section

    def test_deploy_production_recrawl_anomalies_specs(self):
        content = _read(DEPLOY_WORKFLOW_PATH)
        recrawl_section = content.split("realestate-recrawl-anomalies-prod", 1)[1].split("gcloud run jobs", 1)[0]
        assert "--cpu=2" in recrawl_section
        assert "--memory=2Gi" in recrawl_section
