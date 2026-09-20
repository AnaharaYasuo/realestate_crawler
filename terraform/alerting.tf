# ==============================================================================
# Cloud SQL & ProxySQL ログ監視・エラーアラート設計 (Log-based Metrics & Alerting)
# ==============================================================================
# 目的: MySQL 8.0 の認証拒否 (MY-010926 / Access denied) や各種サーバ異常 ([ERROR]、
#       Too many connections / MY-010048) など、通常 NOTICE/DEFAULT 扱いされるログを
#       ログベースメトリクスで捕捉し、重大度 ERROR / CRITICAL のアラートとして即時通知する。

# 1.1 MySQL 認証拒否ログメトリクス (MY-010926 / Access denied for user)
resource "google_logging_metric" "mysql_access_denied_metric" {
  name        = "cloudsql/mysql_access_denied_${var.environment}"
  description = "Count of MySQL authentication failures and access denied logs (MY-010926)"
  filter      = <<-EOT
    resource.type="cloudsql_database"
    AND (textPayload =~ "Access denied for user" OR textPayload =~ "MY-010926")
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "MySQL Access Denied (MY-010926) Count"
  }

  depends_on = [google_project_service.enabled_services]
}

# 1.2 MySQL 認証拒否アラートポリシー (Severity: ERROR)
resource "google_monitoring_alert_policy" "mysql_access_denied_alert" {
  display_name = "Cloud SQL - MySQL Authentication Failure / Access Denied Alert (${var.environment})"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "MySQL Access Denied (MY-010926) > 0"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.mysql_access_denied_metric.name}\" AND resource.type=\"cloudsql_database\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.budget_email[0].name] : []

  alert_strategy {
    auto_close = "1800s" # 30分で自動クローズ
  }

  documentation {
    content   = "MySQL authentication failure detected (MY-010926 / Access denied for user). Investigate ProxySQL credentials, unauthorized access attempts, or application database configuration."
    mime_type = "text/markdown"
  }

  depends_on = [
    google_project_service.enabled_services,
    google_logging_metric.mysql_access_denied_metric
  ]
}

# 2.1 MySQL サーバエラーログメトリクス ([ERROR])
resource "google_logging_metric" "mysql_error_log_metric" {
  name        = "cloudsql/mysql_server_error_${var.environment}"
  description = "Count of MySQL server error logs ([ERROR] severity)"
  filter      = <<-EOT
    resource.type="cloudsql_database"
    AND (severity >= ERROR OR textPayload =~ "\\[ERROR\\]")
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "MySQL Server Error Log Count"
  }

  depends_on = [google_project_service.enabled_services]
}

# 2.2 MySQL サーバエラーアラートポリシー (Severity: ERROR)
resource "google_monitoring_alert_policy" "mysql_error_log_alert" {
  display_name = "Cloud SQL - MySQL Server Error Log Alert (${var.environment})"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "MySQL Server [ERROR] Logs > 0"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.mysql_error_log_metric.name}\" AND resource.type=\"cloudsql_database\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.budget_email[0].name] : []

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "MySQL server logged an [ERROR] event. Check Cloud SQL error logs (cloudsql.googleapis.com/mysql.err) for details."
    mime_type = "text/markdown"
  }

  depends_on = [
    google_project_service.enabled_services,
    google_logging_metric.mysql_error_log_metric
  ]
}

# 3.1 MySQL 接続上限枯渇ログメトリクス (Too many connections / MY-010048)
resource "google_logging_metric" "mysql_too_many_connections_metric" {
  name        = "cloudsql/mysql_too_many_connections_${var.environment}"
  description = "Count of MySQL connection limit reached errors (MY-010048 / Too many connections)"
  filter      = <<-EOT
    resource.type="cloudsql_database"
    AND (textPayload =~ "Too many connections" OR textPayload =~ "MY-010048")
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "MySQL Too Many Connections Count"
  }

  depends_on = [google_project_service.enabled_services]
}

# 3.2 MySQL 接続上限枯渇アラートポリシー (Severity: CRITICAL)
resource "google_monitoring_alert_policy" "mysql_too_many_connections_alert" {
  display_name = "Cloud SQL - MySQL Connection Exhaustion Alert (${var.environment})"
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "MySQL Too Many Connections > 0"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.mysql_too_many_connections_metric.name}\" AND resource.type=\"cloudsql_database\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.budget_email[0].name] : []

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cloud SQL has reached maximum connections (Too many connections / MY-010048). Verify ProxySQL connection multiplexing and pool sizes immediately."
    mime_type = "text/markdown"
  }

  depends_on = [
    google_project_service.enabled_services,
    google_logging_metric.mysql_too_many_connections_metric
  ]
}

# 4. ProxySQL MIG 異常インスタンスアラートポリシー (Severity: ERROR)
resource "google_monitoring_alert_policy" "proxysql_unhealthy_alert" {
  display_name = "ProxySQL - MIG Unhealthy Instances Alert (${var.environment})"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "ProxySQL MIG Unhealthy Instances > 0"
    condition_threshold {
      filter          = "metric.type=\"compute.googleapis.com/instance_group/unhealthy_instances\" AND resource.type=\"instance_group\" AND resource.label.instance_group_name=monitoring.regex.full_match(\"proxysql-mig.*\")"
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.budget_email[0].name] : []

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "One or more ProxySQL instances in the Managed Instance Group are unhealthy. Check MIG status and serial console logs."
    mime_type = "text/markdown"
  }

  depends_on = [
    google_project_service.enabled_services,
    google_compute_region_instance_group_manager.proxysql_mig
  ]
}
