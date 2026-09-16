# Cloud Run Service for Slack Agent & Web APIs (常時待機 / Socket Mode または Webhook)
resource "google_cloud_run_v2_service" "slack_agent_service" {
  name     = "realestate-slack-agent-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_vpc_access_connector.vpc_connector
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
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.crawler_repo.name}/crawler:latest"

      command = ["python", "src/crawler/scripts/ops/run_slack_agent.py"]

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
}
