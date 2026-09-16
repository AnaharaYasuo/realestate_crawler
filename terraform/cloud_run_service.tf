# Cloud Run Service for Slack Agent & Web APIs (常時待機 / Socket Mode または Webhook)
resource "google_cloud_run_v2_service" "slack_agent_service" {
  name     = "realestate-slack-agent-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Socket Mode (WSSアウトバウンド) のため外部インバウンド直接公開を完全遮断

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_vpc_access_connector.vpc_connector,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_version.slack_bot_token_version,
    google_secret_manager_secret_version.slack_app_token_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    service_account = google_service_account.crawler_runner.email

    scaling {
      min_instance_count = 0 # アイドル時0台（コスト削減）。即応性を高める場合は 1 に設定
      max_instance_count = 2
    }

    vpc_access {
      connector = google_vpc_access_connector.vpc_connector.id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.mysql_instance.private_ip_address
      }
      env {
        name  = "DB_NAME"
        value = var.db_name
      }
      env {
        name  = "DB_USER"
        value = var.db_user
      }
      env {
        name  = "DB_PORT"
        value = "3306"
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SLACK_BOT_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.slack_bot_token.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SLACK_APP_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.slack_app_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[0].command
    ]
  }
}
