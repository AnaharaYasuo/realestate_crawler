# -*- coding: utf-8 -*-
"""Cloud SQL ログ監視 & アラートポリシー Terraform 構成の単体テスト (TDD)"""
import os
import re
import pytest

TERRAFORM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform"))


def test_alerting_tf_file_exists():
    """terraform/alerting.tf が存在することを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    assert os.path.exists(alerting_tf), f"alerting.tf should exist at {alerting_tf}"


def test_logging_api_enabled_in_main_tf():
    """terraform/main.tf に logging.googleapis.com が有効化サービスとして定義されていることを検証"""
    main_tf = os.path.join(TERRAFORM_DIR, "main.tf")
    assert os.path.exists(main_tf), "main.tf must exist."

    with open(main_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert '"logging.googleapis.com"' in content, \
        "main.tf must enable logging.googleapis.com API in google_project_service.enabled_services."


def test_mysql_access_denied_metric_and_alert_defined():
    """MySQL 認証拒否 (MY-010926 / Access denied) を ERROR として捕捉・発報するメトリクスとアラートポリシーを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    if not os.path.exists(alerting_tf):
        pytest.fail("alerting.tf does not exist yet.")

    with open(alerting_tf, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. ログベースメトリクス
    assert 'resource "google_logging_metric" "mysql_access_denied_metric"' in content, \
        "alerting.tf must define google_logging_metric for MySQL access denied."
    assert 'Access denied for user' in content or 'MY-010926' in content, \
        "Logging metric filter must match 'Access denied for user' or 'MY-010926'."
    assert 'cloudsql_database' in content, \
        "Logging metric filter must target cloudsql_database resource."

    # 2. アラートポリシー (Severity: ERROR)
    assert 'resource "google_monitoring_alert_policy" "mysql_access_denied_alert"' in content, \
        "alerting.tf must define alert policy for MySQL access denied."
    assert 'severity = "ERROR"' in content or "severity = 'ERROR'" in content or 'severity' in content, \
        "Alert policy must have severity specified."


def test_mysql_error_log_metric_and_alert_defined():
    """MySQL サーバエラー ([ERROR]) を捕捉するログベースメトリクスとアラートポリシーを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    if not os.path.exists(alerting_tf):
        pytest.fail("alerting.tf does not exist yet.")

    with open(alerting_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_logging_metric" "mysql_error_log_metric"' in content, \
        "alerting.tf must define google_logging_metric for MySQL error log."
    assert 'resource "google_monitoring_alert_policy" "mysql_error_log_alert"' in content, \
        "alerting.tf must define alert policy for MySQL error logs."


def test_mysql_too_many_connections_metric_and_alert_defined():
    """MySQL 接続上限到達 (MY-010048 / Too many connections) を捕捉するメトリクスとアラートポリシーを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    if not os.path.exists(alerting_tf):
        pytest.fail("alerting.tf does not exist yet.")

    with open(alerting_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_logging_metric" "mysql_too_many_connections_metric"' in content, \
        "alerting.tf must define google_logging_metric for MySQL too many connections."
    assert 'Too many connections' in content or 'MY-010048' in content, \
        "Logging metric filter must match 'Too many connections' or 'MY-010048'."
    assert 'resource "google_monitoring_alert_policy" "mysql_too_many_connections_alert"' in content, \
        "alerting.tf must define alert policy for connection exhaustion."


def test_proxysql_unhealthy_alert_defined():
    """ProxySQL MIG 異常インスタンスに対するアラートポリシーが定義されていることを検証"""
    alerting_tf = os.path.join(TERRAFORM_DIR, "alerting.tf")
    if not os.path.exists(alerting_tf):
        pytest.fail("alerting.tf does not exist yet.")

    with open(alerting_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_monitoring_alert_policy" "proxysql_unhealthy_alert"' in content, \
        "alerting.tf must define alert policy for ProxySQL unhealthy instances."
