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

    # 2. 単一インスタンスまたはインスタンステンプレート (e2-micro)
    assert (
        re.search(r'resource\s+"google_compute_instance"\s+"proxysql_instance"', content) or
        re.search(r'resource\s+"google_compute_instance_template"\s+"proxysql_template"', content)
    ), "Instance or template for ProxySQL must be defined."
    assert re.search(r'machine_type\s*=\s*(var\.proxysql_machine_type|"e2-micro")', content), \
        "Instance must specify e2-micro machine type."

    # 3. 内部専用IP (単一内部IPまたはILB転送ルール)
    assert (
        re.search(r'resource\s+"google_compute_address"\s+"proxysql_ip"', content) or
        re.search(r'resource\s+"google_compute_forwarding_rule"\s+"proxysql_forwarding_rule"', content)
    ), "Internal static IP or forwarding rule for ProxySQL must be defined."

    # 4. ファイアウォールルール
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


def test_cloud_run_connects_to_proxysql():
    """Cloud Run Job/Service が直接 Cloud SQL ではなく ProxySQL ILB (ポート 6033) に接続していることを検証"""
    job_tf = os.path.join(TERRAFORM_DIR, "cloud_run_job.tf")
    service_tf = os.path.join(TERRAFORM_DIR, "cloud_run_service.tf")
    api_tf = os.path.join(TERRAFORM_DIR, "cloud_run_api_service.tf")

    # 1. Crawler Pipeline Job
    with open(job_tf, "r", encoding="utf-8") as f:
        job_content = f.read()

    assert (
        "google_compute_address.proxysql_ip.address" in job_content or
        "google_compute_forwarding_rule.proxysql_forwarding_rule.ip_address" in job_content
    ), "Crawler Job DB_HOST must route through ProxySQL."
    assert 'name  = "DB_PORT"\n          value = "6033"' in job_content or 'name  = "DB_PORT"\r\n          value = "6033"' in job_content, \
        "Crawler Job DB_PORT must be 6033 (ProxySQL traffic port)."

    # 2. Slack Agent Service
    with open(service_tf, "r", encoding="utf-8") as f:
        service_content = f.read()

    assert (
        "google_compute_address.proxysql_ip.address" in service_content or
        "google_compute_forwarding_rule.proxysql_forwarding_rule.ip_address" in service_content
    ), "Slack Service DB_HOST must route through ProxySQL."
    assert '6033' in service_content, \
        "Slack Service DB_PORT must be 6033."

    # 3. Valuation API Service (Direct to Cloud SQL per #366 for on-demand cost optimization)
    with open(api_tf, "r", encoding="utf-8") as f:
        api_content = f.read()

    assert "google_sql_database_instance.mysql_instance.private_ip_address" in api_content, \
        "Valuation API DB_HOST must route directly to Cloud SQL private IP per #366."
    assert '3306' in api_content, \
        "Valuation API DB_PORT must be 3306."


def test_proxysql_user_authentication():
    """ProxySQL がバックエンド認証用のパスワードを保持していることを検証"""
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    with open(proxysql_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'password="${random_password.db_password.result}"' in content or 'password = "${random_password.db_password.result}"' in content, \
        "ProxySQL mysql_users must configure the real database password for authentication."


def test_app_connection_pool_unrestricted():
    """ProxySQL がプーリング・多重化を一元管理するため、アプリ側プールを廃止し CONN_MAX_AGE=0 に設定されていることを検証"""
    settings_py = os.path.join(os.path.dirname(TERRAFORM_DIR), "src", "crawler", "realestateSettings.py")
    with open(settings_py, "r", encoding="utf-8") as f:
        content = f.read()

    assert "dj_db_conn_pool" not in content, \
        "App side pooling (dj_db_conn_pool) must be removed to delegate connection management entirely to ProxySQL."
    assert "'CONN_MAX_AGE': 0" in content, \
        "App side CONN_MAX_AGE must be set to 0 to prevent connection retention in containers."


def test_proxysql_monitor_user_configured():
    """ProxySQL の内部死活監視用 monitor ユーザーおよびパスワードが正しく構成されていることを検証"""
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    database_tf = os.path.join(TERRAFORM_DIR, "database.tf")
    secrets_tf = os.path.join(TERRAFORM_DIR, "secrets.tf")

    with open(proxysql_tf, "r", encoding="utf-8") as f:
        proxysql_content = f.read()

    with open(database_tf, "r", encoding="utf-8") as f:
        db_content = f.read()

    with open(secrets_tf, "r", encoding="utf-8") as f:
        secrets_content = f.read()

    # 1. database.tf に monitor ユーザーとパスワードが定義されていること
    assert 'resource "random_password" "db_monitor_password"' in db_content, \
        "database.tf must define random_password.db_monitor_password for health checks."
    assert 'resource "google_sql_user" "monitor_user"' in db_content, \
        "database.tf must define google_sql_user.monitor_user for ProxySQL."
    assert 'name     = "monitor"' in db_content or 'name = "monitor"' in db_content, \
        "google_sql_user.monitor_user must have name='monitor'."

    # 2. secrets.tf に保管されていること
    assert 'realestate-db-monitor-password-' in secrets_content, \
        "secrets.tf must store db_monitor_password in Secret Manager."

    # 3. proxysql.tf の mysql_variables に monitor_username と monitor_password が設定されていること
    assert 'monitor_username="monitor"' in proxysql_content or 'monitor_username = "monitor"' in proxysql_content, \
        "proxysql.tf mysql_variables must explicitly configure monitor_username."
    assert 'monitor_password="${random_password.db_monitor_password.result}"' in proxysql_content or \
           'monitor_password = "${random_password.db_monitor_password.result}"' in proxysql_content, \
        "proxysql.tf mysql_variables must configure monitor_password using the random password."
    assert 'monitor_ping_interval' in proxysql_content, \
        "proxysql.tf mysql_variables must tune monitor_ping_interval."
    assert 'monitor_read_only_interval' in proxysql_content, \
        "proxysql.tf mysql_variables must tune monitor_read_only_interval."


def test_proxysql_admin_credentials_not_default():
    """ProxySQL 管理認証情報がデフォルトの admin:admin ではなくセキュアなランダムパスワードであることを検証"""
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    secrets_tf = os.path.join(TERRAFORM_DIR, "secrets.tf")

    with open(proxysql_tf, "r", encoding="utf-8") as f:
        proxysql_content = f.read()

    with open(secrets_tf, "r", encoding="utf-8") as f:
        secrets_content = f.read()

    # デフォルトの静的 admin:admin が排除されていること
    assert 'admin_credentials="admin:admin;radmin:radmin"' not in proxysql_content, \
        "Default admin:admin;radmin:radmin credentials must not be used in proxysql.cnf."
    assert 'random_password.proxysql_admin_password' in proxysql_content, \
        "ProxySQL admin credentials must use dynamic random password."
    assert 'realestate-proxysql-admin-password-' in secrets_content, \
        "secrets.tf must store proxysql_admin_password in Secret Manager."


def test_proxysql_zombie_running_alert_filter():
    """ProxySQL 稼働監視・エラー監視アラートポリシーが alerting.tf に定義されていることを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    with open(alerting_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert (
        'resource "google_monitoring_alert_policy" "proxysql_error_alert"' in content or
        'resource "google_monitoring_alert_policy" "proxysql_zombie_running_alert"' in content or
        'resource "google_monitoring_alert_policy" "proxysql_uptime_alert"' in content
    ), "alerting.tf must define ProxySQL alert policy."



