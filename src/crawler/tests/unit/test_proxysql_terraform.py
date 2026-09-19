# -*- coding: utf-8 -*-
"""ProxySQL Terraform 構成の単体テスト (TDD)"""
import os
import re
import pytest

TERRAFORM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform"))


def test_proxysql_tf_file_exists():
    """terraform/proxysql.tf が存在することを検証"""
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    assert os.path.exists(proxysql_tf), f"proxysql.tf should exist at {proxysql_tf}"


def test_proxysql_resources_defined():
    """ProxySQL 関連の必須リソースが正しく定義されていることを検証"""
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    if not os.path.exists(proxysql_tf):
        pytest.fail("proxysql.tf does not exist yet.")

    with open(proxysql_tf, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. サービスアカウント
    assert re.search(r'resource\s+"google_service_account"\s+"proxysql_sa"', content), \
        "Dedicated service account for ProxySQL must be defined."

    # 2. インスタンステンプレート (e2-micro)
    assert re.search(r'resource\s+"google_compute_instance_template"\s+"proxysql_template"', content), \
        "Instance template for ProxySQL must be defined."
    assert 'machine_type = "e2-micro"' in content or 'machine_type = var.proxysql_machine_type' in content, \
        "Instance template must specify e2-micro machine type."

    # 3. MIG (リージョン配置, 2ゾーン分散)
    assert re.search(r'resource\s+"google_compute_region_instance_group_manager"\s+"proxysql_mig"', content), \
        "Region instance group manager (MIG) for ProxySQL must be defined."
    assert re.search(r'max_surge_fixed\s*=\s*2', content), \
        "max_surge_fixed must be at least 2 for regional MIG with 2 zones."

    # 3.1 オートスケーラー (Min 1, Max 2, CPU連動)
    assert re.search(r'resource\s+"google_compute_region_autoscaler"\s+"proxysql_autoscaler"', content), \
        "Region autoscaler for ProxySQL must be defined."
    assert re.search(r'min_replicas\s*=\s*(1|var\.proxysql_min_replicas)', content), \
        "Autoscaler min_replicas must be 1."
    assert re.search(r'max_replicas\s*=\s*(2|var\.proxysql_max_replicas)', content), \
        "Autoscaler max_replicas must be 2."

    # 4. ヘルスチェック (TCP: 6033)
    assert re.search(r'resource\s+"google_compute_region_health_check"\s+"proxysql_health_check"', content), \
        "Region health check for ProxySQL must be defined."
    assert re.search(r'port\s*=\s*6033', content), \
        "Health check must probe port 6033 (traffic port)."

    # 5. ILB バックエンドサービス (INTERNAL, TCP, Connection Draining)
    assert re.search(r'resource\s+"google_compute_region_backend_service"\s+"proxysql_backend"', content), \
        "Region backend service for ILB must be defined."
    assert 'load_balancing_scheme = "INTERNAL"' in content, \
        "Backend service load_balancing_scheme must be INTERNAL."
    assert re.search(r'protocol\s*=\s*"TCP"', content), \
        "Backend service protocol must be TCP."
    assert re.search(r'connection_draining_timeout_sec\s*=\s*\d+', content), \
        "Backend service must configure connection draining to protect in-flight queries during scale-in."

    # 6. 転送ルール (Forwarding Rule for ILB)
    assert re.search(r'resource\s+"google_compute_forwarding_rule"\s+"proxysql_forwarding_rule"', content), \
        "Forwarding rule for ILB must be defined."
    assert '6033' in content, \
        "Forwarding rule must handle port 6033."

    # 7. ファイアウォールルール
    assert re.search(r'resource\s+"google_compute_firewall"\s+"allow_proxysql_health_check"', content), \
        "Firewall rule to allow GCP health checks must be defined."
    assert '35.191.0.0/16' in content and '130.211.0.0/22' in content, \
        "Firewall rule must allow Google Cloud health check IP ranges."
    assert re.search(r'resource\s+"google_compute_firewall"\s+"allow_proxysql_internal"', content), \
        "Firewall rule for internal VPC traffic must be defined."


def test_proxysql_outputs_defined():
    """terraform/outputs.tf に ProxySQL ILB の出力が定義されていることを検証"""
    outputs_tf = os.path.join(TERRAFORM_DIR, "outputs.tf")
    assert os.path.exists(outputs_tf), "outputs.tf must exist."

    with open(outputs_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'output "proxysql_ilb_ip"' in content, \
        "outputs.tf must include proxysql_ilb_ip output."


def test_proxysql_variables_defined():
    """terraform/variables.tf に ProxySQL 関連のチューニング変数が定義されていることを検証"""
    variables_tf = os.path.join(TERRAFORM_DIR, "variables.tf")
    assert os.path.exists(variables_tf), "variables.tf must exist."

    with open(variables_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'variable "proxysql_backend_max_connections"' in content or 'variable "proxysql_max_connections"' in content, \
        "variables.tf must include variable for ProxySQL backend connections tuning."
    assert 'variable "proxysql_min_replicas"' in content, \
        "variables.tf must include proxysql_min_replicas variable."
    assert 'variable "proxysql_max_replicas"' in content, \
        "variables.tf must include proxysql_max_replicas variable."
