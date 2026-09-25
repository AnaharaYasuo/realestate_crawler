# -*- coding: utf-8 -*-
import os

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)


def test_terraform_dispatcher_and_ml_jobs_defined():
    """terraform/cloud_run_job.tf に Dispatcher Job と ML Pipeline Job が定義されていることを検証"""
    job_file = os.path.join(TERRAFORM_DIR, "cloud_run_job.tf")
    assert os.path.exists(job_file), f"{job_file} must exist"

    with open(job_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_cloud_run_v2_job" "crawler_dispatcher_job"' in content, \
        "cloud_run_job.tf must define crawler_dispatcher_job"
    assert 'resource "google_cloud_run_v2_job" "ml_pipeline_job"' in content, \
        "cloud_run_job.tf must define ml_pipeline_job"


def test_terraform_crawler_worker_service_defined():
    """terraform/cloud_run_crawler_service.tf に Crawler Worker サービスが定義され、ProxySQL ILB へのルートと VPC Egress が設定されていることを検証"""
    worker_file = os.path.join(TERRAFORM_DIR, "cloud_run_crawler_service.tf")
    assert os.path.exists(worker_file), f"{worker_file} must exist"

    with open(worker_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_cloud_run_v2_service" "crawler_worker_service"' in content, \
        "cloud_run_crawler_service.tf must define crawler_worker_service"
    assert "realestate-crawler-worker-" in content, \
        "crawler_worker_service must have name realestate-crawler-worker-${var.environment}"
    assert "proxysql_forwarding_rule" in content or "proxysql_ip" in content, \
        "crawler_worker_service must route DB_HOST to ProxySQL (forwarding rule or static IP)"
